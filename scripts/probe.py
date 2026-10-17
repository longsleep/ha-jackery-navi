#!/usr/bin/env python3
"""Poll a Navi from a laptop with the integration's own protocol module — no Home Assistant needed.

    python scripts/probe.py 74:4D:BD:XX:XX:XX            # identity + every ID the integration reads
    python scripts/probe.py 74:4D:BD:XX:XX:XX -v         # also the raw frames

Needs bleak and bleak-retry-connector. Read-only: it sends device_get and data_get, nothing else.
"""

import argparse
import asyncio
import importlib.util
import json
import logging
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "navi_ble", HERE.parent / "custom_components" / "jackery_navi" / "navi_ble.py"
)
navi_ble = importlib.util.module_from_spec(spec)
sys.modules["navi_ble"] = navi_ble
spec.loader.exec_module(navi_ble)

from bleak import BleakScanner  # noqa: E402

# Mirrors const.SENSORS, which cannot be imported without Home Assistant.
REQUESTS = {
    "ems": [16932865, 16934913, 21548033, 21549057, 21550081, 21556225, 16939009, 16935937, 23132161,
            23135233, 23136257, 23286785, 23120897, 29929473, 25753601, 25749505, 16961537, 16966657,
            16967681, 16962561, 16968705],
    "pcs": [50490369, 50490370, 50382849, 50392065, 50394113, 50894849, 50895873],
    "bms1": [33605633, 33606657, 33659905, 37848065, 37849089],
}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("address")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    device = await BleakScanner.find_device_by_address(args.address, timeout=20)
    if device is None:
        raise SystemExit(f"{args.address} not found")
    serial = (device.name or "").removeprefix("Jackery_")
    started = time.monotonic()
    data = await navi_ble.poll(device, serial, REQUESTS, with_device_info=True)
    print(f"poll took {time.monotonic() - started:.1f} s")
    identity = {k: v for k, v in (data.device_info or {}).items() if k != "dev_list"}
    print("identity:", json.dumps(identity))
    for dev in (data.device_info or {}).get("dev_list", []):
        print("  sub-device:", dev.get("dev_type"), dev.get("soft_ver"), dev.get("factory"))
    missing = [(p, i) for p, ids in REQUESTS.items() for i in ids if (p, i) not in data.values]
    for (prefix, meter_id), value in sorted(data.values.items()):
        print(f"{prefix:5} {meter_id:>10} {value}")
    print("missing:", missing or "none")


asyncio.run(main())
