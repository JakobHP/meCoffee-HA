"""Sensor platform for meCoffee PID integration."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from datetime import timedelta

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
    _attr_name = "Boiler temperature"
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
    _attr_name = "Setpoint temperature"
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
    _attr_name = "Second sensor temperature"
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
    _attr_name = "PID power"
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:gauge"

    @property
    def native_value(self) -> float | None:
        """Return the PID power, defaulting to 0 before first pid line."""
        value = self.coordinator.device.telemetry.get("pid_power")
        if value is None and self.coordinator.device.is_connected:
            return 0.0
        return value


class ShotTimerSensor(MeCoffeeSensor):
    """Sensor for shot timer with client-side counting.

    While a shot is active, a 1-second interval timer ticks the displayed
    value up using monotonic clock math.  When the shot ends, the sensor
    locks to the firmware-reported duration.  Defaults to 0.0 (not Unknown)
    until the first shot is pulled.
    """

    _attr_translation_key = "shot_timer"
    _attr_name = "Shot timer"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: MeCoffeeCoordinator,
        key: str,
    ) -> None:
        """Initialize the shot timer sensor."""
        super().__init__(coordinator, key)
        self._cancel_timer: CALLBACK_TYPE | None = None
        self._was_active = False

    @property
    def native_value(self) -> float:
        """Return the shot timer value.

        While a shot is active, computes elapsed time from the monotonic
        start timestamp.  Otherwise returns the last firmware-reported
        duration (or 0.0 if no shot has been pulled yet).
        """
        telemetry = self.coordinator.device.telemetry
        if telemetry.get("shot_timer_active"):
            elapsed = time.monotonic() - telemetry.get("shot_timer_start", 0.0)
            return round(elapsed, 1)
        value = telemetry.get("shot_timer")
        return value if value is not None else 0.0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator data update — start/stop the tick timer."""
        active = self.coordinator.device.telemetry.get("shot_timer_active", False)

        if active and not self._was_active:
            # Shot just started — begin ticking every second
            self._start_tick_timer()
        elif not active and self._was_active:
            # Shot just ended — stop ticking
            self._stop_tick_timer()

        self._was_active = active
        super()._handle_coordinator_update()

    def _start_tick_timer(self) -> None:
        """Start a 1-second interval to update the displayed elapsed time."""
        self._stop_tick_timer()
        self._cancel_timer = async_track_time_interval(
            self.hass,
            self._tick,
            timedelta(seconds=1),
        )

    def _stop_tick_timer(self) -> None:
        """Cancel the tick timer if running."""
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    @callback
    def _tick(self, _now: Any) -> None:
        """Update the sensor display on each tick."""
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up the tick timer when the entity is removed."""
        self._stop_tick_timer()
        await super().async_will_remove_from_hass()


class FirmwareVersionSensor(MeCoffeeSensor):
    """Sensor for firmware version."""

    _attr_translation_key = "firmware_version"
    _attr_name = "Firmware version"
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
