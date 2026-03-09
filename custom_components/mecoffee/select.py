"""Select platform for meCoffee PID integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeCoffeeConfigEntry
from .const import (
    KEY_OUTPUT_0,
    KEY_OUTPUT_1,
    KEY_OUTPUT_2,
    OUTPUT_OPTIONS,
)
from .coordinator import MeCoffeeCoordinator

_LOGGER = logging.getLogger(__name__)

# Create reverse mapping: label → code
OPTION_TO_CODE = {v: k for k, v in OUTPUT_OPTIONS.items()}


@dataclass(frozen=True)
class MeCoffeeSelectDescription(SelectEntityDescription):
    """Extended select description for meCoffee devices."""

    mecoffee_key: str = ""


SELECT_DESCRIPTIONS: tuple[MeCoffeeSelectDescription, ...] = (
    MeCoffeeSelectDescription(
        key="output_0",
        translation_key="output_0",
        icon="mdi:electric-switch",
        mecoffee_key=KEY_OUTPUT_0,
    ),
    MeCoffeeSelectDescription(
        key="output_1",
        translation_key="output_1",
        icon="mdi:electric-switch",
        mecoffee_key=KEY_OUTPUT_1,
    ),
    MeCoffeeSelectDescription(
        key="output_2",
        translation_key="output_2",
        icon="mdi:electric-switch",
        mecoffee_key=KEY_OUTPUT_2,
    ),
)


class MeCoffeeSelect(CoordinatorEntity[MeCoffeeCoordinator], SelectEntity):
    """Select entity for meCoffee output assignments."""

    _attr_has_entity_name = True
    entity_description: MeCoffeeSelectDescription

    def __init__(
        self,
        coordinator: MeCoffeeCoordinator,
        description: MeCoffeeSelectDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device.address}_{description.key}"
        self._attr_device_info = coordinator.device_info
        self._attr_options = list(OUTPUT_OPTIONS.values())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        code = self.coordinator.device.get_scaled_value(
            self.entity_description.mecoffee_key
        )
        if code is None:
            return None
        return OUTPUT_OPTIONS.get(code)

    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        code = OPTION_TO_CODE.get(option)
        if code is None:
            return
        try:
            await self.coordinator.device.async_set_value(
                self.entity_description.mecoffee_key,
                code,
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
    """Set up meCoffee select entities from a config entry."""
    coordinator: MeCoffeeCoordinator = entry.runtime_data

    entities = [
        MeCoffeeSelect(coordinator, description)
        for description in SELECT_DESCRIPTIONS
    ]

    async_add_entities(entities)
