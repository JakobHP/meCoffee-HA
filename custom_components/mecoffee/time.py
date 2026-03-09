"""Time platform for meCoffee PID integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeCoffeeConfigEntry
from .const import KEY_SHUTDOWN_TIME, KEY_WAKE_TIME
from .coordinator import MeCoffeeCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MeCoffeeTimeDescription(TimeEntityDescription):
    """Describes a meCoffee time entity."""

    mecoffee_key: str = ""


TIME_DESCRIPTIONS = [
    MeCoffeeTimeDescription(
        key="wake_time",
        translation_key="wake_time",
        name="Wake-up time",
        icon="mdi:alarm",
        entity_category=EntityCategory.CONFIG,
        mecoffee_key=KEY_WAKE_TIME,
    ),
    MeCoffeeTimeDescription(
        key="shutdown_time",
        translation_key="shutdown_time",
        name="Shutdown time",
        icon="mdi:power-sleep",
        entity_category=EntityCategory.CONFIG,
        mecoffee_key=KEY_SHUTDOWN_TIME,
    ),
]


class MeCoffeeTime(CoordinatorEntity[MeCoffeeCoordinator], TimeEntity):
    """Time entity for meCoffee settings."""

    _attr_has_entity_name = True
    entity_description: MeCoffeeTimeDescription

    def __init__(
        self,
        coordinator: MeCoffeeCoordinator,
        description: MeCoffeeTimeDescription,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.address}_{description.key}"
        )
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> dt_time | None:
        """Return the current time value."""
        seconds = self.coordinator.device.get_scaled_value(
            self.entity_description.mecoffee_key
        )
        if seconds is None:
            return None

        # Convert seconds since midnight to time
        seconds = int(seconds)
        hour = seconds // 3600
        minute = (seconds % 3600) // 60
        second = seconds % 60

        return dt_time(hour, minute, second)

    async def async_set_value(self, value: dt_time) -> None:
        """Set the time value."""
        # Convert time to seconds since midnight
        seconds = value.hour * 3600 + value.minute * 60 + value.second

        try:
            await self.coordinator.device.async_set_value(
                self.entity_description.mecoffee_key,
                seconds,
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Failed to set {self.entity_description.key}: {err}"
            ) from err

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeCoffeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up time entities from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        MeCoffeeTime(coordinator, description)
        for description in TIME_DESCRIPTIONS
    )
