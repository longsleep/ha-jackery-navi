"""Jackery Navi 2000, read locally over Bluetooth (including through ESPHome Bluetooth proxies)."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SERIAL
from .coordinator import NaviConfigEntry, NaviCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NaviConfigEntry) -> bool:
    address: str = entry.data[CONF_ADDRESS]
    if bluetooth.async_ble_device_from_address(hass, address, connectable=True) is None:
        raise ConfigEntryNotReady(
            f"Jackery Navi {address} is not in range of any connectable Bluetooth adapter or proxy"
        )
    coordinator = NaviCoordinator(hass, entry, address, entry.data[CONF_SERIAL])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NaviConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
