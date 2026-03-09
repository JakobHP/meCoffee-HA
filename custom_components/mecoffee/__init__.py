"""The meCoffee PID integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .coordinator import MeCoffeeCoordinator
from .mecoffee_device import MeCoffeeDevice

_LOGGER = logging.getLogger(__name__)

type MeCoffeeConfigEntry = ConfigEntry[MeCoffeeCoordinator]

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


async def async_setup_entry(hass: HomeAssistant, entry: MeCoffeeConfigEntry) -> bool:
    """Set up meCoffee PID from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    name: str = entry.data.get("name", "meCoffee")

    device = MeCoffeeDevice(address, name)
    coordinator = MeCoffeeCoordinator(hass, entry, device)

    # Store coordinator on the entry for platform access.
    entry.runtime_data = coordinator

    # Do the first refresh — this connects BLE + waits for init.
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeCoffeeConfigEntry) -> bool:
    """Unload a meCoffee config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: MeCoffeeCoordinator = entry.runtime_data
        await coordinator.async_shutdown()
    return unload_ok
