"""DataUpdateCoordinator for meCoffee PID."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from bleak.exc import BleakError

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    KEY_AUTO_SHUTOFF,
    KEY_SHUTDOWN_ENABLE,
    KEY_SHUTDOWN_TIME,
)
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

        # Local auto-shutoff: the firmware's tmrosd inactivity timer does
        # not work while a BLE client is connected (the connection itself
        # counts as activity).  We replicate the behaviour locally by
        # tracking the last real user activity (shots, setting changes)
        # and triggering a shutdown via the firmware's scheduled-shutdown
        # timer trick when the idle period exceeds the configured tmrosd.
        self._auto_shutoff_running = False
        self._cancel_idle_check: CALLBACK_TYPE | None = None
        # Saved timer settings to restore after the shutdown sequence.
        self._saved_shutdown_time: int | None = None
        self._saved_shutdown_enable: bool | None = None

        # Register for disconnect notifications from the device layer.
        device.set_on_disconnect(self._on_device_disconnect)

        # Register for real-time telemetry pushes from the device layer.
        device.set_on_telemetry(self._on_telemetry_update)

    def register_advertisement_callback(self, entry: ConfigEntry) -> None:
        """Register a BLE advertisement callback for instant reconnection.

        When the meCoffee device starts advertising (machine powered on),
        this callback fires and immediately resets the reconnection backoff,
        triggering an instant coordinator refresh instead of waiting up to
        5 minutes for the next scheduled retry.

        Must be called after the coordinator is created.  The unregister
        callable is attached to the config entry via ``async_on_unload``
        so it is automatically removed when the entry is unloaded.
        """
        @callback
        def _on_advertisement(
            service_info: BluetoothServiceInfoBleak,
            change: BluetoothChange,
        ) -> None:
            """Handle a BLE advertisement from the meCoffee device."""
            if self.device.is_connected:
                return  # Already connected — nothing to do.

            if self._consecutive_failures == 0:
                return  # Not in backoff — normal polling will handle it.

            _LOGGER.info(
                "meCoffee advertisement detected while disconnected "
                "(backoff index %d) — resetting backoff for instant reconnect",
                self._consecutive_failures,
            )
            self._consecutive_failures = 0
            self.update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
            self.hass.async_create_task(self.async_request_refresh())

        entry.async_on_unload(
            async_register_callback(
                self.hass,
                _on_advertisement,
                BluetoothCallbackMatcher(address=self.device.address),
                BluetoothScanningMode.PASSIVE,
            )
        )

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
        self._stop_idle_check()
        self.async_set_updated_data(self._build_data())

    @callback
    def _on_telemetry_update(self) -> None:
        """Handle real-time telemetry push from the device.

        Called from the BLE notification handler whenever a tmp, pid, or
        sht line is parsed (~1/second while connected).  Pushes the latest
        data to all entities immediately, giving real-time sensor updates
        without waiting for the coordinator's poll interval.

        We update self.data directly and notify listeners instead of calling
        async_set_updated_data(), which logs a misleading "Manually updated"
        debug line on every push (~1/second).
        """
        self.data = self._build_data()
        self.async_update_listeners()

    def _build_data(self) -> dict[str, Any]:
        """Build the coordinator data dict from current device state."""
        return {
            "settings": dict(self.device.settings),
            "telemetry": dict(self.device.telemetry),
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

                # Restore shutdown settings if a previous auto-shutoff
                # sequence couldn't restore them (device disconnected
                # before restoration completed).
                if (
                    self._saved_shutdown_time is not None
                    or self._saved_shutdown_enable is not None
                ):
                    await self._restore_shutdown_settings()

                # Start the local auto-shutoff idle check.
                self._start_idle_check()

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

        return self._build_data()

    # ── Local auto-shutoff ─────────────────────────────────────────────

    def _start_idle_check(self) -> None:
        """Start the periodic idle check timer.

        Called once after the first successful connection.  Runs every 30
        seconds and compares elapsed idle time against the configured
        tmrosd value.
        """
        if self._cancel_idle_check is not None:
            return  # Already running.

        self._cancel_idle_check = async_track_time_interval(
            self.hass,
            self._check_idle,
            timedelta(seconds=30),
        )

    def _stop_idle_check(self) -> None:
        """Stop the periodic idle check timer."""
        if self._cancel_idle_check is not None:
            self._cancel_idle_check()
            self._cancel_idle_check = None

    @callback
    def _check_idle(self, _now: Any) -> None:
        """Check if the machine has been idle longer than tmrosd allows.

        Runs every 30 seconds while connected.  If the user-configured
        auto-shutoff time (tmrosd, in minutes) has elapsed since the last
        real activity, trigger the shutdown sequence.
        """
        if self._auto_shutoff_running:
            return  # Shutdown already in progress.

        if not self.device.is_connected:
            return

        # Read the configured auto-shutoff time (minutes).
        shutoff_minutes = self.device.get_scaled_value(KEY_AUTO_SHUTOFF)
        if shutoff_minutes is None or int(shutoff_minutes) == 0:
            return  # Auto-shutoff disabled.

        idle_seconds = time.monotonic() - self.device.last_activity
        shutoff_seconds = int(shutoff_minutes) * 60

        if idle_seconds >= shutoff_seconds:
            _LOGGER.info(
                "Machine idle for %d minutes (limit %d) — "
                "initiating local auto-shutoff",
                int(idle_seconds // 60),
                int(shutoff_minutes),
            )
            self.hass.async_create_task(self._execute_auto_shutoff())

    async def _execute_auto_shutoff(self) -> None:
        """Shut down the machine using the scheduled-shutdown timer trick.

        Sequence:
        1. Save current shutdown-time and shutdown-enable settings.
        2. Set the shutdown time to the next whole minute.
        3. Enable the shutdown timer.
        4. Poll PID power until the firmware shuts down (power → 0%).
        5. Restore the original shutdown settings.
        """
        self._auto_shutoff_running = True
        device = self.device

        try:
            # 1. Save current values.
            raw_time = device.settings.get(KEY_SHUTDOWN_TIME)
            self._saved_shutdown_time = (
                int(raw_time) if isinstance(raw_time, (int, float)) else None
            )
            raw_enable = device.settings.get(KEY_SHUTDOWN_ENABLE)
            self._saved_shutdown_enable = (
                bool(raw_enable) if raw_enable is not None else None
            )

            # 2. Compute target time: next whole minute, ~5 s from now.
            now = datetime.now()
            target = now + timedelta(seconds=5)
            # Round up to the next whole minute.
            if target.second > 0:
                target = target + timedelta(seconds=(60 - target.second))
            target_seconds = target.hour * 3600 + target.minute * 60

            _LOGGER.debug(
                "Auto-shutoff: setting shutdown time to %02d:%02d",
                target.hour,
                target.minute,
            )

            # 3. Set shutdown time and enable the timer.
            await device.async_set_value(
                KEY_SHUTDOWN_TIME, target_seconds, _internal=True
            )
            await asyncio.sleep(0.3)
            await device.async_set_value(
                KEY_SHUTDOWN_ENABLE, True, _internal=True
            )

            # 4. Poll PID power to detect the shutdown.
            # The firmware checks the shutdown timer at minute boundaries.
            # When it acts, PID power drops to 0% (heater off).  We poll
            # every 2 seconds, requiring 3 consecutive zero readings to
            # confirm (avoids false positives from brief PID dips).
            # Hard timeout at 90 s in case the firmware doesn't act.
            _LOGGER.info("Auto-shutoff: waiting for firmware to shut down")
            consecutive_zero = 0
            deadline = time.monotonic() + 90

            while time.monotonic() < deadline:
                if not device.is_connected:
                    _LOGGER.info(
                        "Auto-shutoff: device disconnected during wait "
                        "(firmware likely shut down)"
                    )
                    break

                pid_power = device.telemetry.get("pid_power")
                if pid_power is not None and pid_power == 0.0:
                    consecutive_zero += 1
                    if consecutive_zero >= 3:
                        _LOGGER.info(
                            "Auto-shutoff: PID power at 0%% for %d checks "
                            "— shutdown confirmed",
                            consecutive_zero,
                        )
                        break
                else:
                    consecutive_zero = 0

                await asyncio.sleep(2)
            else:
                _LOGGER.warning(
                    "Auto-shutoff: timed out waiting for firmware to shut "
                    "down (PID power still active after 90 s)"
                )

            # 5. Restore original settings.
            await self._restore_shutdown_settings()

        except BleakError as err:
            _LOGGER.warning("Auto-shutoff sequence failed: %s", err)
        finally:
            self._auto_shutoff_running = False

    async def _restore_shutdown_settings(self) -> None:
        """Restore the shutdown timer settings saved before auto-shutoff."""
        device = self.device

        if not device.is_connected:
            _LOGGER.debug(
                "Auto-shutoff: device disconnected, "
                "will restore settings on next connect"
            )
            # Keep saved values — they'll be restored on next reconnect.
            return

        try:
            if self._saved_shutdown_time is not None:
                await device.async_set_value(
                    KEY_SHUTDOWN_TIME, self._saved_shutdown_time, _internal=True
                )
                await asyncio.sleep(0.3)

            if self._saved_shutdown_enable is not None:
                await device.async_set_value(
                    KEY_SHUTDOWN_ENABLE, self._saved_shutdown_enable, _internal=True
                )

            _LOGGER.debug("Auto-shutoff: original shutdown settings restored")
        except BleakError as err:
            _LOGGER.warning(
                "Auto-shutoff: failed to restore shutdown settings: %s", err
            )
            # Keep saved values for retry on next reconnect.
            return

        self._saved_shutdown_time = None
        self._saved_shutdown_enable = None

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def async_shutdown(self) -> None:
        """Disconnect on shutdown."""
        self._stop_idle_check()
        await super().async_shutdown()
        await self.device.disconnect()
