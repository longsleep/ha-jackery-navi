"""Adding a Navi: from Bluetooth discovery, by picking from the Navis in range, or by address."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_SERIAL, DOMAIN, NAME_PREFIX, NAVI_NAME_PREFIX, serial_from_name

MANUAL = "manual"


def _is_navi(name: str | None) -> bool:
    return bool(name) and name.startswith(NAVI_NAME_PREFIX)


class NaviConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for a Jackery Navi 2000 reached over Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._in_range: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        """HA heard a ``Jackery_HA…`` advert through an adapter or proxy."""
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()
        if not _is_navi(discovery_info.name):
            return self.async_abort(reason="not_supported")
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._discovery is not None
        if user_input is not None:
            return self._create(self._discovery.address, self._discovery.name)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovery.name, "address": self._discovery.address},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick one of the Navis currently in range, or choose to enter an address."""
        if user_input is not None:
            choice = user_input[CONF_ADDRESS]
            if choice == MANUAL:
                return await self.async_step_manual()
            info = self._in_range[choice]
            await self.async_set_unique_id(format_mac(info.address), raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self._create(info.address, info.name)

        configured = self._async_current_ids(include_ignore=False)
        self._in_range = {
            info.address: info
            for info in async_discovered_service_info(self.hass, connectable=True)
            if _is_navi(info.name) and format_mac(info.address) not in configured
        }
        if not self._in_range:
            return await self.async_step_manual()

        choices = {
            address: f"{info.name} ({address}, {info.rssi} dBm)"
            for address, info in sorted(self._in_range.items(), key=lambda item: -item[1].rssi)
        }
        choices[MANUAL] = "Enter a Bluetooth address…"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(choices)}),
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add a Navi by address; it must be heard by some adapter or proxy at that moment."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            await self.async_set_unique_id(format_mac(address), raise_on_progress=False)
            self._abort_if_unique_id_configured()
            device = async_ble_device_from_address(self.hass, address, connectable=True)
            if device is None:
                errors["base"] = "not_in_range"
            elif not (device.name or "").startswith(NAME_PREFIX):
                errors["base"] = "not_jackery"
            else:
                return self._create(address, device.name)
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )

    def _create(self, address: str, name: str) -> ConfigFlowResult:
        return self.async_create_entry(
            title=name,
            data={CONF_ADDRESS: address, CONF_SERIAL: serial_from_name(name)},
        )
