"""DataUpdateCoordinator for meCoffee PID."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from bleak.exc import BleakError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .mecoffee_device import MeCoffeeDevice

_LOGGER = logging.getLogger(__name__)


class MeCoffeeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that manages BLE connection and polling for a meCoffee device."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: MeCoffeeDevice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device.name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.device = device
        self._first_update = True

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info for the device registry."""
        return {
            "identifiers": {(DOMAIN, self.device.address)},
            "name": self.device.name,
            "manufacturer": "meCoffee",
            "model": "meCoffee PID",
            "sw_version": self.device.firmware_version,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device.

        On first update: connect and wait for init + dump.
        On subsequent updates: the device streams telemetry continuously
        via notifications, so we just return current state.
        We periodically re-request a dump to keep settings fresh.
        """
        try:
            if not self.device.is_connected:
                await self.device.connect(self.hass)
                await self.device.async_wait_for_init(timeout=20.0)
                # After init, wait a bit for dump results to arrive
                self._first_update = True

            if self._first_update:
                self._first_update = False
                # The init sequence already sends cmd dump.
                # Give it time to complete.
                import asyncio
                await asyncio.sleep(3.0)

        except BleakError as err:
            raise UpdateFailed(f"BLE connection failed: {err}") from err
        except TimeoutError as err:
            raise UpdateFailed(f"BLE connection timed out: {err}") from err

        return {
            "settings": dict(self.device.settings),
            "telemetry": dict(self.device.telemetry),
            "firmware_version": self.device.firmware_version,
            "legacy": self.device.legacy,
        }

    async def async_shutdown(self) -> None:
        """Disconnect on shutdown."""
        await super().async_shutdown()
        await self.device.disconnect()
