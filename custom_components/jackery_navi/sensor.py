"""Sensor entities for the Jackery Navi 2000."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import SENSORS, NaviSensorDescription
from .coordinator import NaviConfigEntry, NaviCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NaviConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(NaviSensor(coordinator, description) for description in SENSORS)


class NaviSensor(CoordinatorEntity[NaviCoordinator], SensorEntity):
    """One meter ID of one sub-device."""

    _attr_has_entity_name = True
    entity_description: NaviSensorDescription

    def __init__(self, coordinator: NaviCoordinator, description: NaviSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}-{description.dev}-{description.meter_id}"
        self._attr_device_info = coordinator.device_info

    @property
    def _raw(self) -> str | None:
        data = self.coordinator.data
        if data is None:
            return None
        return data.values.get((self.entity_description.dev, self.entity_description.meter_id))

    @property
    def available(self) -> bool:
        return super().available and self._raw is not None

    @property
    def native_value(self) -> StateType:
        raw = self._raw
        if raw is None:
            return None
        description = self.entity_description
        if description.value_fn is not None:
            return description.value_fn(raw)
        try:
            return float(raw) * description.scale
        except ValueError:
            return None
