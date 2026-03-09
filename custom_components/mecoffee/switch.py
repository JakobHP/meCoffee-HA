"""Switch platform for meCoffee PID integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeCoffeeConfigEntry
from .const import (
    KEY_CONTINUOUS_MODE,
    KEY_PREINFUSION_CLOSE_VALVE,
    KEY_PREINFUSION_ENABLE,
    KEY_POWER_FLIP,
    KEY_SHUTDOWN_ENABLE,
    KEY_TIMER_POWER,
    KEY_WAKE_ENABLE,
)
from .coordinator import MeCoffeeCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MeCoffeeSwitchDescription(SwitchEntityDescription):
    """Extended switch description for meCoffee devices."""

    mecoffee_key: str = ""


SWITCH_DESCRIPTIONS: tuple[MeCoffeeSwitchDescription, ...] = (
    MeCoffeeSwitchDescription(
        key="continuous_mode",
        translation_key="continuous_mode",
        name="Continuous mode",
        icon="mdi:infinity",
        entity_category=EntityCategory.CONFIG,
        mecoffee_key=KEY_CONTINUOUS_MODE,
    ),
    MeCoffeeSwitchDescription(
        key="preinfusion_enable",
        translation_key="preinfusion_enable",
        name="Preinfusion",
        icon="mdi:water-pump",
        entity_category=EntityCategory.CONFIG,
        mecoffee_key=KEY_PREINFUSION_ENABLE,
    ),
    MeCoffeeSwitchDescription(
        key="preinfusion_close_valve",
        translation_key="preinfusion_close_valve",
        name="Preinfusion close valve",
        icon="mdi:valve-closed",
        entity_category=EntityCategory.CONFIG,
        mecoffee_key=KEY_PREINFUSION_CLOSE_VALVE,
    ),
    MeCoffeeSwitchDescription(
        key="wake_enable",
        translation_key="wake_enable",
        name="Wake timer",
        icon="mdi:alarm",
        entity_category=EntityCategory.CONFIG,
        mecoffee_key=KEY_WAKE_ENABLE,
    ),
    MeCoffeeSwitchDescription(
        key="shutdown_enable",
        translation_key="shutdown_enable",
        name="Shutdown timer",
        icon="mdi:power-sleep",
        entity_category=EntityCategory.CONFIG,
        mecoffee_key=KEY_SHUTDOWN_ENABLE,
    ),
    MeCoffeeSwitchDescription(
        key="timer_power_mode",
        translation_key="timer_power_mode",
        name="Timer power mode",
        icon="mdi:timer-cog",
        entity_category=EntityCategory.CONFIG,
        mecoffee_key=KEY_TIMER_POWER,
    ),
    MeCoffeeSwitchDescription(
        key="power_button_flip",
        translation_key="power_button_flip",
        name="Power button flip",
        icon="mdi:swap-horizontal",
        entity_category=EntityCategory.CONFIG,
        mecoffee_key=KEY_POWER_FLIP,
    ),
)


class MeCoffeeSwitch(CoordinatorEntity[MeCoffeeCoordinator], SwitchEntity):
    """Switch entity for meCoffee boolean settings."""

    _attr_has_entity_name = True
    entity_description: MeCoffeeSwitchDescription

    def __init__(
        self,
        coordinator: MeCoffeeCoordinator,
        description: MeCoffeeSwitchDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device.address}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        value = self.coordinator.device.get_scaled_value(
            self.entity_description.mecoffee_key
        )
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the switch."""
        try:
            await self.coordinator.device.async_set_value(
                self.entity_description.mecoffee_key,
                True,
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Failed to turn on {self.entity_description.key}: {err}"
            ) from err
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the switch."""
        try:
            await self.coordinator.device.async_set_value(
                self.entity_description.mecoffee_key,
                False,
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Failed to turn off {self.entity_description.key}: {err}"
            ) from err
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeCoffeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up meCoffee switch entities from a config entry."""
    coordinator: MeCoffeeCoordinator = entry.runtime_data

    entities = [
        MeCoffeeSwitch(coordinator, description)
        for description in SWITCH_DESCRIPTIONS
    ]

    async_add_entities(entities)
