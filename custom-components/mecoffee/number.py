from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    device = hass.data[DOMAIN][entry.entry_id]

    entities = [
        MeCoffeeTemperatureNumber(device),
    ]

    async_add_entities(entities)


class MeCoffeeTemperatureNumber(NumberEntity):
    """Temperature setpoint control."""

    _attr_name = "Target Temperature"
    _attr_native_min_value = 80
    _attr_native_max_value = 120
    _attr_native_step = 0.5
    _attr_unit_of_measurement = "°C"

    def __init__(self, device):
        self._device = device
        self._value = None

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set target temperature."""
        self._value = value
        await self._device.set_target_temperature(value)
        self.async_write_ha_state()
