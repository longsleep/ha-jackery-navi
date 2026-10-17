"""Constants and the meter-ID table for the Jackery Navi 2000."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.helpers.typing import StateType

DOMAIN = "jackery_navi"
CONF_SERIAL = "serial"

NAME_PREFIX = "Jackery_"
# Navi 2000 serials start HA2A; the HomePower 2000 Ultra (HL2B…) shares the protocol but not this table.
NAVI_NAME_PREFIX = "Jackery_HA"

UPDATE_INTERVAL = timedelta(seconds=30)

BATTERY_STATES = {"0": "idle", "1": "charging", "2": "discharging"}


def serial_from_name(name: str) -> str:
    """``Jackery_HA2A…`` → ``HA2A…``; the advertised name carries the gateway serial."""
    return name.removeprefix(NAME_PREFIX)


@dataclass(frozen=True, kw_only=True)
class NaviSensorDescription(SensorEntityDescription):
    """A reading: which sub-device answers it, its meter ID, and how to turn the string into a value."""

    dev: str
    meter_id: int
    scale: float = 1.0
    value_fn: Callable[[str], StateType] | None = None


def _text(raw: str) -> StateType:
    return raw


def _battery_state(raw: str) -> StateType:
    return BATTERY_STATES.get(raw)


# Only IDs whose meaning was cross-checked on a real Navi 2000. Names in comments are the vendor's own
# property names, from the property map the Jackery Home app ships.
SENSORS: tuple[NaviSensorDescription, ...] = (
    # EMS
    NaviSensorDescription(
        key="pv_power", name="PV power", dev="ems", meter_id=16932865,
        native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="ac_power", name="AC grid port power", dev="ems", meter_id=16934913,
        native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="battery_soc", name="Battery", dev="ems", meter_id=21548033, scale=0.1,
        native_unit_of_measurement=PERCENTAGE, device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
    ),
    NaviSensorDescription(
        key="battery_energy", name="Battery energy", dev="ems", meter_id=21549057,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR, device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="battery_capacity", name="Battery capacity", dev="ems", meter_id=21550081,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR, device_class=SensorDeviceClass.ENERGY_STORAGE,
        entity_category=EntityCategory.DIAGNOSTIC, suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="battery_state", name="Battery state", dev="ems", meter_id=21556225,
        device_class=SensorDeviceClass.ENUM, options=list(BATTERY_STATES.values()),
        value_fn=_battery_state,
    ),
    # HB-EMS-MODEL_heatLossPower. Checked by energy balance: grid in 1199 W − battery in 1088 W = 111 W, against
    # a reading of 112.1.
    NaviSensorDescription(
        key="conversion_loss", name="Conversion loss", dev="ems", meter_id=16939009,
        native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    # HB-EMS-MODEL_smartSocketPower: the enrolled Shelly plugs together.
    NaviSensorDescription(
        key="smart_plug_power", name="Smart plug power", dev="ems", meter_id=16935937,
        native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="work_mode", name="Work mode (raw)", dev="ems", meter_id=23132161,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=_text,
    ),
    NaviSensorDescription(
        key="charge_limit", name="Charge limit", dev="ems", meter_id=23135233, scale=0.1,
        native_unit_of_measurement=PERCENTAGE, entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="discharge_limit", name="Discharge limit", dev="ems", meter_id=23136257, scale=0.1,
        native_unit_of_measurement=PERCENTAGE, entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="max_feed_in", name="Max feed-in", dev="ems", meter_id=23286785,
        native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC, suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="ac_socket", name="AC socket (raw)", dev="ems", meter_id=23120897,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=_text,
    ),
    NaviSensorDescription(
        key="wifi_rssi", name="Wi-Fi signal", dev="ems", meter_id=29929473,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH, state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
    ),
    NaviSensorDescription(
        key="power_board_firmware", name="Power board firmware", dev="ems", meter_id=25753601,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=_text,
    ),
    NaviSensorDescription(
        key="wifi_firmware", name="Wi-Fi firmware", dev="ems", meter_id=25749505,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=_text,
    ),
    # Lifetime counters, kWh, for the Energy dashboard. PV1 + PV2 equals the PV total to the hundredth.
    NaviSensorDescription(
        key="pv_energy", name="PV energy", dev="ems", meter_id=16961537,  # pvTotalCharge
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2,
    ),
    NaviSensorDescription(
        key="pv1_energy", name="PV1 energy", dev="ems", meter_id=16966657,  # pv1TotalGen
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2,
    ),
    NaviSensorDescription(
        key="pv2_energy", name="PV2 energy", dev="ems", meter_id=16967681,  # pv2TotalGen
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2,
    ),
    NaviSensorDescription(
        key="ac_energy_in", name="AC grid port energy in", dev="ems", meter_id=16962561,  # onGridTotalUse
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2,
    ),
    NaviSensorDescription(
        key="ac_energy_out", name="AC grid port energy out", dev="ems", meter_id=16968705,  # onGridGenTotal
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2,
    ),
    # PCS
    NaviSensorDescription(
        key="pv1_power", name="PV1 power", dev="pcs", meter_id=50490369,
        native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="pv2_power", name="PV2 power", dev="pcs", meter_id=50490370,
        native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="grid_voltage", name="Grid voltage", dev="pcs", meter_id=50382849,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
    ),
    NaviSensorDescription(
        key="grid_frequency", name="Grid frequency", dev="pcs", meter_id=50392065,
        native_unit_of_measurement=UnitOfFrequency.HERTZ, device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
    ),
    NaviSensorDescription(
        key="grid_power", name="Grid power (PCS)", dev="pcs", meter_id=50394113,
        native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    # 50591745 is HB-PCS-MODEL_loadRaP, a load rate rather than a temperature: not exposed.
    NaviSensorDescription(
        key="pcs_heat_sink_temperature", name="PCS heat sink temperature", dev="pcs", meter_id=50894849,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    NaviSensorDescription(
        key="pcs_inverter_temperature", name="PCS inverter temperature", dev="pcs", meter_id=50895873,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    # BMS
    NaviSensorDescription(
        key="battery_voltage", name="Battery voltage", dev="bms1", meter_id=33605633, scale=0.1,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
    ),
    # Decoded by energy balance on 2026-10-11: current × voltage matched the power figure to
    # within 2 W, and the lifetime counters moved with the charge and discharge seen that day.
    NaviSensorDescription(
        key="battery_current", name="Battery current", dev="bms1", meter_id=33606657, scale=0.1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
    ),
    NaviSensorDescription(
        key="battery_power", name="Battery power", dev="bms1", meter_id=33659905,
        native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="battery_energy_charged", name="Battery energy charged", dev="bms1", meter_id=37848065,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR, device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=0,
    ),
    NaviSensorDescription(
        key="battery_energy_discharged", name="Battery energy discharged", dev="bms1", meter_id=37849089,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR, device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=0,
    ),
)


def poll_requests() -> dict[str, list[int]]:
    """The meter IDs to ask each sub-device for, in table order."""
    requests: dict[str, list[int]] = {}
    for description in SENSORS:
        requests.setdefault(description.dev, []).append(description.meter_id)
    return requests
