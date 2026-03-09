"""Number platform for meCoffee PID integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeCoffeeConfigEntry
from .const import (
    KEY_AUTO_SHUTOFF,
    KEY_BREW_TEMP,
    KEY_MAX_SHOT_TIME,
    KEY_PID_D,
    KEY_PID_I,
    KEY_PID_I_MAX,
    KEY_PID_I_MIN,
    KEY_PID_INTERVAL,
    KEY_PID_P,
    KEY_PRESSURE_END,
    KEY_PRESSURE_PERIOD,
    KEY_PRESSURE_START,
    KEY_PREINFUSION_PAUSE_TIME,
    KEY_PREINFUSION_PUMP_TIME,
    KEY_PROACTIVE_PCT,
    KEY_STEAM_TEMP,
)
from .coordinator import MeCoffeeCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MeCoffeeNumberDescription(NumberEntityDescription):
    """Extended number description for meCoffee devices."""

    mecoffee_key: str = ""


NUMBER_DESCRIPTIONS: tuple[MeCoffeeNumberDescription, ...] = (
    MeCoffeeNumberDescription(
        key="brew_temperature",
        translation_key="brew_temperature",
        native_min_value=50,
        native_max_value=125,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_BREW_TEMP,
    ),
    MeCoffeeNumberDescription(
        key="steam_temperature",
        translation_key="steam_temperature",
        native_min_value=110,
        native_max_value=140,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_STEAM_TEMP,
    ),
    MeCoffeeNumberDescription(
        key="proactive_percent",
        translation_key="proactive_percent",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        mecoffee_key=KEY_PROACTIVE_PCT,
    ),
    MeCoffeeNumberDescription(
        key="pid_proportional",
        translation_key="pid_proportional",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_PID_P,
    ),
    MeCoffeeNumberDescription(
        key="pid_integral",
        translation_key="pid_integral",
        native_min_value=0,
        native_max_value=1,
        native_step=0.01,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_PID_I,
    ),
    MeCoffeeNumberDescription(
        key="pid_derivative",
        translation_key="pid_derivative",
        native_min_value=0,
        native_max_value=256,
        native_step=1,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_PID_D,
    ),
    MeCoffeeNumberDescription(
        key="pid_i_wind_down_min",
        translation_key="pid_i_wind_down_min",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_PID_I_MIN,
    ),
    MeCoffeeNumberDescription(
        key="pid_i_wind_down_max",
        translation_key="pid_i_wind_down_max",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_PID_I_MAX,
    ),
    MeCoffeeNumberDescription(
        key="pid_interval",
        translation_key="pid_interval",
        native_min_value=1000,
        native_max_value=10000,
        native_step=500,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_PID_INTERVAL,
    ),
    MeCoffeeNumberDescription(
        key="pressure_start",
        translation_key="pressure_start",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        mecoffee_key=KEY_PRESSURE_START,
    ),
    MeCoffeeNumberDescription(
        key="pressure_end",
        translation_key="pressure_end",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        mecoffee_key=KEY_PRESSURE_END,
    ),
    MeCoffeeNumberDescription(
        key="pressure_period",
        translation_key="pressure_period",
        native_min_value=0,
        native_max_value=60,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_PRESSURE_PERIOD,
    ),
    MeCoffeeNumberDescription(
        key="preinfusion_pump_time",
        translation_key="preinfusion_pump_time",
        native_min_value=0,
        native_max_value=10,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_PREINFUSION_PUMP_TIME,
    ),
    MeCoffeeNumberDescription(
        key="preinfusion_pause_time",
        translation_key="preinfusion_pause_time",
        native_min_value=0,
        native_max_value=10,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_PREINFUSION_PAUSE_TIME,
    ),
    MeCoffeeNumberDescription(
        key="max_shot_time",
        translation_key="max_shot_time",
        native_min_value=0,
        native_max_value=60,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_MAX_SHOT_TIME,
    ),
    MeCoffeeNumberDescription(
        key="auto_shutoff",
        translation_key="auto_shutoff",
        native_min_value=0,
        native_max_value=120,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        mecoffee_key=KEY_AUTO_SHUTOFF,
    ),
)


class MeCoffeeNumber(CoordinatorEntity[MeCoffeeCoordinator], NumberEntity):
    """Number entity for meCoffee settings."""

    _attr_has_entity_name = True
    entity_description: MeCoffeeNumberDescription

    def __init__(
        self,
        coordinator: MeCoffeeCoordinator,
        description: MeCoffeeNumberDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device.address}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | int | None:
        """Return the native value of the number."""
        value = self.coordinator.device.get_scaled_value(
            self.entity_description.mecoffee_key
        )
        if value is None:
            return None
        return float(value) if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value."""
        await self.coordinator.device.async_set_value(
            self.entity_description.mecoffee_key,
            value,
        )
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeCoffeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up meCoffee number entities from a config entry."""
    coordinator: MeCoffeeCoordinator = entry.runtime_data

    entities = [
        MeCoffeeNumber(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    ]

    async_add_entities(entities)
