"""Sensor platform for meCoffee PID integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeCoffeeConfigEntry
from .coordinator import MeCoffeeCoordinator

_LOGGER = logging.getLogger(__name__)


class MeCoffeeSensor(CoordinatorEntity[MeCoffeeCoordinator], SensorEntity):
    """Base class for meCoffee sensor entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MeCoffeeCoordinator,
        key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.device.address}_{key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        raise NotImplementedError


class BoilerTemperatureSensor(MeCoffeeSensor):
    """Sensor for boiler temperature."""

    _attr_translation_key = "boiler_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the boiler temperature."""
        return self.coordinator.device.telemetry.get("boiler_temp")


class SetpointTemperatureSensor(MeCoffeeSensor):
    """Sensor for setpoint temperature."""

    _attr_translation_key = "setpoint_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the setpoint temperature."""
        return self.coordinator.device.telemetry.get("setpoint_temp")


class SecondSensorTemperatureSensor(MeCoffeeSensor):
    """Sensor for second sensor temperature."""

    _attr_translation_key = "second_sensor_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> float | None:
        """Return the second sensor temperature."""
        return self.coordinator.device.telemetry.get("second_sensor_temp")


class PIDPowerSensor(MeCoffeeSensor):
    """Sensor for PID power output."""

    _attr_translation_key = "pid_power"
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:gauge"

    @property
    def native_value(self) -> float | None:
        """Return the PID power."""
        return self.coordinator.device.telemetry.get("pid_power")


class ShotTimerSensor(MeCoffeeSensor):
    """Sensor for shot timer."""

    _attr_translation_key = "shot_timer"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer"

    @property
    def native_value(self) -> float | None:
        """Return the shot timer."""
        return self.coordinator.device.telemetry.get("shot_timer")


class FirmwareVersionSensor(MeCoffeeSensor):
    """Sensor for firmware version."""

    _attr_translation_key = "firmware_version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    @property
    def native_value(self) -> str | None:
        """Return the firmware version."""
        return self.coordinator.device.firmware_version


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeCoffeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up meCoffee sensors from a config entry."""
    coordinator: MeCoffeeCoordinator = entry.runtime_data

    entities = [
        BoilerTemperatureSensor(coordinator, "boiler_temp"),
        SetpointTemperatureSensor(coordinator, "setpoint_temp"),
        SecondSensorTemperatureSensor(coordinator, "second_sensor_temp"),
        PIDPowerSensor(coordinator, "pid_power"),
        ShotTimerSensor(coordinator, "shot_timer"),
        FirmwareVersionSensor(coordinator, "firmware_version"),
    ]

    async_add_entities(entities)
