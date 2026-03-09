"""DataUpdateCoordinator for meCoffee PID."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from bleak.exc import BleakError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .mecoffee_device import MeCoffeeDevice

_LOGGER = logging.getLogger(__name__)

# Back-off schedule for reconnection attempts (seconds).
# After each failed reconnect, we move to the next interval.
# This prevents hammering a powered-off device every 10 seconds.
_BACKOFF_SCHEDULE = [10, 30, 60, 120, 300]  # 10s, 30s, 1m, 2m, 5m max


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
        self._consecutive_failures = 0

        # Register for disconnect notifications from the device layer.
        device.set_on_disconnect(self._on_device_disconnect)

    @callback
    def _on_device_disconnect(self) -> None:
        """Handle unexpected device disconnection.

        This is called from the bleak disconnect callback (runs in the
        event loop) when the BLE link drops — typically because the
        espresso machine was powered off.

        We immediately request a coordinator refresh so that:
          1. Entities see the UpdateFailed and go unavailable right away.
          2. The next _async_update_data call enters the reconnect path.
        """
        _LOGGER.info("meCoffee device disconnected — entities will go unavailable")
        self.async_set_updated_data(self._unavailable_data())

    def _unavailable_data(self) -> dict[str, Any]:
        """Return a data dict that represents an unavailable device.

        Returning this through async_set_updated_data keeps entities
        "available" from the coordinator's perspective (no UpdateFailed),
        but all sensor values will be None, so HA shows them as "unknown".
        We'll mark the coordinator as actually failed on the *next* poll
        when reconnection fails, which flips entities to "unavailable".
        """
        return {
            "settings": dict(self.device.settings),
            "telemetry": dict(self.device.telemetry),  # already cleared
            "firmware_version": self.device.firmware_version,
            "legacy": self.device.legacy,
        }

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

        Connection lifecycle:
        - If connected: return current telemetry/settings (streamed via notify).
        - If disconnected: attempt reconnect with exponential back-off.
        - On reconnect success: reset back-off, re-init, dump settings.
        - On reconnect failure: raise UpdateFailed → entities go unavailable.
          The coordinator's built-in interval keeps retrying automatically.
        """
        try:
            if not self.device.is_connected:
                _LOGGER.debug(
                    "Device not connected, attempting reconnect "
                    "(attempt backoff index %d)",
                    self._consecutive_failures,
                )
                await self.device.connect(self.hass)
                await self.device.async_wait_for_init(timeout=20.0)

                # Connection succeeded — reset failure tracking
                self._consecutive_failures = 0
                self.update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
                self._first_update = True
                _LOGGER.info(
                    "Reconnected to %s — entities will become available",
                    self.device.name,
                )

            if self._first_update:
                self._first_update = False
                # The init sequence already sends cmd dump.
                # Give it time to complete.
                await asyncio.sleep(3.0)

        except (BleakError, TimeoutError) as err:
            # Apply back-off: increase the poll interval so we don't
            # spam reconnect attempts every 10s when the machine is off.
            self._consecutive_failures += 1
            backoff_idx = min(
                self._consecutive_failures - 1, len(_BACKOFF_SCHEDULE) - 1
            )
            backoff_seconds = _BACKOFF_SCHEDULE[backoff_idx]
            self.update_interval = timedelta(seconds=backoff_seconds)

            _LOGGER.debug(
                "Reconnect to %s failed (%s), next attempt in %ds",
                self.device.name,
                err,
                backoff_seconds,
            )
            raise UpdateFailed(
                f"Device unavailable (off or out of range): {err}"
            ) from err

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
