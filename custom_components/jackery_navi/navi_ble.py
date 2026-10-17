"""The Jackery Navi 2000 Bluetooth protocol.

The link is Espressif BluFi: GATT service 0xFFFF, writes to 0xFF01 (with response only), notifications on
0xFF02. Jackery's requests and replies are JSON documents carried in BluFi "custom data" frames, unencrypted.

Frame layout, both directions::

    type  frame-control  seq  data-length  data…
    0x4D  0x00 / 0x10    n    len          JSON bytes

``type`` 0x4D is a BluFi data frame of subtype 0x13 (custom data); 0x49 is subtype 0x12, an error report
carrying one byte. In frame control, 0x10 marks a fragment (the data then starts with the remaining total
length as two octets, little-endian) and 0x04 marks the device-to-phone direction. The length field is one
octet, so no frame carries more than 255 octets of data, whatever the MTU.

The phone's sequence number starts at 0 on every connection and counts every frame sent; the device drops a
frame with the wrong number and reports an error. A reply may span more than one BluFi message — the
device's identity reply does — so replies are collected until they parse as JSON.

Nothing here imports Home Assistant, so the module can be exercised directly with bleak.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import time
from dataclasses import dataclass, field

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

_LOGGER = logging.getLogger(__name__)

WRITE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

TYPE_CUSTOM_DATA = 0x4D
TYPE_ERROR_REPORT = 0x49
FC_ENCRYPTED = 0x01
FC_FRAGMENT = 0x10

# The data-length field is one octet; 252 is what the vendor app uses (a 250-octet chunk plus the 2-octet
# remaining length).
MAX_FRAME_DATA = 252
ATT_OVERHEAD = 3
FRAME_HEADER = 4

REQUEST_TIMEOUT = 10.0


class NaviError(Exception):
    """The device refused a request or answered with something unusable."""


def encode_frames(payload: bytes, seq: int, max_data: int) -> list[bytes]:
    """Split one JSON payload into BluFi custom-data frames, numbering them from ``seq``."""
    frames: list[bytes] = []
    while len(payload) > max_data:
        chunk = payload[: max_data - 2]
        frames.append(
            bytes((TYPE_CUSTOM_DATA, FC_FRAGMENT, seq & 0xFF, len(chunk) + 2))
            + len(payload).to_bytes(2, "little")
            + chunk
        )
        payload = payload[len(chunk) :]
        seq += 1
    frames.append(bytes((TYPE_CUSTOM_DATA, 0x00, seq & 0xFF, len(payload))) + payload)
    return frames


class FrameAssembler:
    """Turns notifications back into whole BluFi messages."""

    def __init__(self) -> None:
        self._fragments = bytearray()

    def feed(self, frame: bytes) -> tuple[str, bytes] | None:
        """Take one notification; return ``("data", message)`` or ``("error", code)`` when one completes."""
        if len(frame) < FRAME_HEADER:
            return None
        ftype, control, _seq, length = frame[:FRAME_HEADER]
        data = frame[FRAME_HEADER : FRAME_HEADER + length]
        if control & FC_ENCRYPTED:
            raise NaviError("device sent an encrypted frame; this client does not negotiate BluFi security")
        if ftype == TYPE_ERROR_REPORT:
            return ("error", data)
        if ftype != TYPE_CUSTOM_DATA:
            return None
        if control & FC_FRAGMENT:
            self._fragments += data[2:]
            return None
        message = bytes(self._fragments) + data
        self._fragments.clear()
        return ("data", message)


class NaviSession:
    """Requests and replies over one open connection."""

    def __init__(self, client: BleakClient, serial: str) -> None:
        self._client = client
        self._serial = serial
        self._seq = 0
        self._assembler = FrameAssembler()
        self._queue: asyncio.Queue[tuple[str, bytes]] = asyncio.Queue()

    async def start(self) -> None:
        await self._client.start_notify(NOTIFY_UUID, self._on_notify)

    def _on_notify(self, _characteristic: object, data: bytearray) -> None:
        _LOGGER.debug("<- %s", bytes(data).hex())
        try:
            item = self._assembler.feed(bytes(data))
        except NaviError as err:
            item = ("error", str(err).encode())
        if item is not None:
            self._queue.put_nowait(item)

    def _max_frame_data(self) -> int:
        mtu = getattr(self._client, "mtu_size", 23) or 23
        return max(8, min(mtu - ATT_OVERHEAD - FRAME_HEADER, MAX_FRAME_DATA))

    async def request(self, cmd: str, info: dict, timeout: float = REQUEST_TIMEOUT) -> dict:
        """Send one command and return the device's reply document."""
        message: dict = {
            "cmd": cmd,
            "gw_sn": self._serial,
            "timestamp": str(int(time.time() * 1000)),
            "info": info,
        }
        if cmd != "device_get":
            message["token"] = str(random.randint(10**8, 10**9 - 1))
        payload = json.dumps(message, separators=(",", ":")).encode()

        while not self._queue.empty():
            self._queue.get_nowait()

        frames = encode_frames(payload, self._seq, self._max_frame_data())
        for frame in frames:
            _LOGGER.debug("-> %s", frame.hex())
            await self._client.write_gatt_char(WRITE_UUID, frame, response=True)
        self._seq += len(frames)

        collected = b""
        async with asyncio.timeout(timeout):
            while True:
                kind, data = await self._queue.get()
                if kind == "error":
                    raise NaviError(f"{cmd}: device reported error {data.hex() or data!r}")
                collected += data
                try:
                    reply = json.loads(collected)
                except ValueError:
                    continue
                if reply.get("cmd") != cmd:
                    collected = b""
                    continue
                return reply


@dataclass
class NaviData:
    """One poll's worth of readings, keyed by ``(sub-device prefix, meter ID)``."""

    values: dict[tuple[str, int], str] = field(default_factory=dict)
    device_info: dict | None = None


async def _negotiate_mtu(client: BleakClient) -> None:
    """Ask BlueZ for the real MTU before anything reads it; proxies report theirs without asking."""
    backend = getattr(client, "_backend", None)
    acquire = getattr(backend, "_acquire_mtu", None)
    if acquire is None or getattr(backend, "_mtu_size", 0) is not None:
        return
    with contextlib.suppress(Exception):
        await acquire()


async def poll(
    ble_device: BLEDevice,
    serial: str,
    requests: dict[str, list[int]],
    with_device_info: bool = False,
) -> NaviData:
    """Connect, read the requested meter IDs per sub-device, disconnect.

    ``requests`` maps a sub-device prefix (``ems``, ``pcs``, ``bms1``) to the meter IDs to read from
    ``<prefix>_<serial>``. IDs the device does not know are left out of its reply, not reported as errors.
    """
    client = await establish_connection(
        BleakClientWithServiceCache, ble_device, ble_device.name or serial, max_attempts=3
    )
    try:
        await _negotiate_mtu(client)
        session = NaviSession(client, serial)
        await session.start()
        data = NaviData()
        if with_device_info:
            data.device_info = (await session.request("device_get", {})).get("info", {})
        for prefix, ids in requests.items():
            reply = await session.request(
                "data_get",
                {"dev_list": [{"dev_sn": f"{prefix}_{serial}", "meter_list": [str(i) for i in ids]}]},
            )
            info = reply.get("info", {})
            if info.get("result", "0") != "0":
                raise NaviError(f"data_get {prefix}: result {info.get('result')} {info.get('reason')!r}")
            for device in info.get("dev_list", []):
                for meter_id, value in device.get("meter_list", []):
                    data.values[(prefix, int(meter_id))] = value
        return data
    finally:
        await client.disconnect()
