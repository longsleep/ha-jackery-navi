"""Polls one Navi 2000 over Bluetooth, through whichever adapter or proxy hears it."""

from __future__ import annotations

import logging

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, poll_requests
from .navi_ble import NaviData, NaviError, poll

_LOGGER = logging.getLogger(__name__)

type NaviConfigEntry = ConfigEntry[NaviCoordinator]


class NaviCoordinator(DataUpdateCoordinator[NaviData]):
    """One connection per poll: the Navi accepts a single central, so the slot is held only briefly."""

    config_entry: NaviConfigEntry

    def __init__(self, hass: HomeAssistant, entry: NaviConfigEntry, address: str, serial: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"Jackery Navi {serial}",
            update_interval=UPDATE_INTERVAL,
        )
        self.address = address
        self.serial = serial
        self.identity: dict | None = None
        self._requests = poll_requests()

    async def _async_update_data(self) -> NaviData:
        ble_device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
        if ble_device is None:
            raise UpdateFailed(
                f"{self.address} is not in range of any connectable Bluetooth adapter or proxy"
            )
        try:
            data = await poll(ble_device, self.serial, self._requests, with_device_info=self.identity is None)
        except (BleakError, NaviError, TimeoutError) as err:
            raise UpdateFailed(f"Polling the Navi failed: {err}") from err
        if data.device_info is not None:
            self.identity = data.device_info
        return data

    @property
    def device_info(self) -> DeviceInfo:
        identity = self.identity or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            connections={(CONNECTION_BLUETOOTH, self.address)},
            name="Jackery Navi 2000",
            manufacturer="Jackery",
            model="Navi 2000",
            serial_number=self.serial,
            sw_version=identity.get("soft_ver"),
        )
