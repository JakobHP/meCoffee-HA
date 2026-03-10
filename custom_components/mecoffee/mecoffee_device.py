"""BLE serial protocol handler for meCoffee PID devices.

Handles connecting to the HM-10/CC2541 BLE module, sending commands,
and parsing newline-delimited responses and telemetry.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant

from .const import (
    BOOLEAN_KEYS,
    INTEGER_KEYS,
    LEGACY_SCALE_FACTORS,
    MECOFFEE_CHAR_UUID,
    MECOFFEE_SERVICE_UUID,
    SCALE_FACTORS,
    STRING_KEYS,
)

_LOGGER = logging.getLogger(__name__)

# How many startup lines to receive before sending initialization commands.
# The Android app waits for teller_input_lines == 3.
_INIT_LINE_COUNT = 3

# Maximum time to wait for a cmd dump response to complete.
_DUMP_TIMEOUT = 15.0


class MeCoffeeDevice:
    """Manages BLE communication with a meCoffee PID controller."""

    def __init__(self, address: str, name: str) -> None:
        """Initialize the device."""
        self.address = address
        self.name = name

        # Connection state
        self._client: BleakClient | None = None
        self._connect_lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()
        self._hass: HomeAssistant | None = None
        self._on_disconnect_callback: Callable[[], None] | None = None
        self._on_telemetry_callback: Callable[[], None] | None = None

        # Receive buffer for newline-delimited protocol
        self._rx_buffer = ""
        self._line_count = 0
        self._initialized = False
        self._init_event = asyncio.Event()

        # Parsed data
        self.settings: dict[str, int | float | bool | str] = {}
        self.telemetry: dict[str, Any] = {
            "boiler_temp": None,
            "setpoint_temp": None,
            "second_sensor_temp": None,
            "pid_power": 0.0,
            "shot_timer": 0.0,
            "shot_timer_active": False,
            "shot_timer_start": 0.0,  # monotonic timestamp
        }
        self.firmware_version: str | None = None
        self.legacy: bool = False

        # Activity tracking for local auto-shutoff.
        # Updated on shot events, setting writes, and initial connection.
        self.last_activity: float = time.monotonic()

        # Dump synchronization
        self._dump_event = asyncio.Event()
        self._dump_keys_received: set[str] = set()
        self._awaiting_dump = False

    def set_on_disconnect(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when the device unexpectedly disconnects."""
        self._on_disconnect_callback = callback

    def set_on_telemetry(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when new telemetry data arrives.

        This fires on every parsed tmp, pid, or sht line (~1/second while
        connected) so the coordinator can push real-time entity updates.
        """
        self._on_telemetry_callback = callback

    def record_activity(self) -> None:
        """Record user activity to reset the local auto-shutoff timer.

        Called on shot events and user-initiated setting changes.
        NOT called on passive telemetry (tmp, pid) which would defeat
        the purpose of the inactivity timer.
        """
        self.last_activity = time.monotonic()

    @property
    def is_connected(self) -> bool:
        """Return True if currently connected."""
        return self._client is not None and self._client.is_connected

    def _clear_telemetry(self) -> None:
        """Reset telemetry values so entities report unavailable."""
        self.telemetry = {
            "boiler_temp": None,
            "setpoint_temp": None,
            "second_sensor_temp": None,
            "pid_power": None,
            "shot_timer": None,
            "shot_timer_active": False,
            "shot_timer_start": 0.0,
        }

    def _handle_disconnect(self, _client: BleakClient) -> None:
        """Handle unexpected BLE disconnection (e.g. device powered off)."""
        _LOGGER.info(
            "Device %s (%s) disconnected", self.name, self.address
        )
        self._client = None
        self._initialized = False
        self._init_event.clear()
        self._rx_buffer = ""
        self._line_count = 0
        self._clear_telemetry()

        if self._on_disconnect_callback is not None:
            self._on_disconnect_callback()

    async def connect(self, hass: HomeAssistant) -> None:
        """Establish BLE connection and start notifications."""
        async with self._connect_lock:
            if self.is_connected:
                return

            self._hass = hass

            ble_device = async_ble_device_from_address(hass, self.address, connectable=True)
            if ble_device is None:
                raise BleakError(f"Device {self.address} not found")

            self._rx_buffer = ""
            self._line_count = 0
            self._initialized = False
            self._init_event.clear()

            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.name,
                disconnected_callback=self._handle_disconnect,
            )

            try:
                # Start notifications on the serial characteristic.
                # The HM-10 module uses a single characteristic for both TX and RX.
                await client.start_notify(
                    MECOFFEE_CHAR_UUID,
                    self._notification_handler,
                )
            except Exception:
                await client.disconnect()
                raise

            self._client = client
            self.record_activity()
            _LOGGER.info("Connected to %s (%s)", self.name, self.address)

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        async with self._connect_lock:
            if self._client is not None:
                try:
                    await self._client.disconnect()
                except BleakError:
                    _LOGGER.debug("Error disconnecting from %s", self.name)
                finally:
                    self._client = None
                    self._initialized = False
                    self._clear_telemetry()

    async def _write(self, data: str) -> None:
        """Write a string to the BLE characteristic."""
        if self._client is None or not self._client.is_connected:
            raise BleakError("Not connected")

        encoded = data.encode("utf-8")
        # HM-10 module has 20-byte MTU for writes.
        # Split into chunks if necessary.
        chunk_size = 20
        for i in range(0, len(encoded), chunk_size):
            chunk = encoded[i : i + chunk_size]
            await self._client.write_gatt_char(
                MECOFFEE_CHAR_UUID,
                chunk,
                response=False,
            )

    def _notification_handler(
        self, _sender: Any, data: bytearray
    ) -> None:
        """Handle incoming BLE notifications (serial data fragments)."""
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            _LOGGER.debug("Non-UTF8 data received: %s", data.hex())
            return

        self._rx_buffer += text

        # Process complete lines
        while "\n" in self._rx_buffer:
            line, self._rx_buffer = self._rx_buffer.split("\n", 1)
            line = line.strip("\r").strip()
            if line:
                self._process_line(line)

    def _process_line(self, line: str) -> None:
        """Process a single received line from the device."""
        self._line_count += 1

        # Schedule initialization after receiving enough startup lines
        if self._line_count == _INIT_LINE_COUNT and not self._initialized:
            self._initialized = True
            if self._hass is not None:
                self._hass.async_create_task(self._send_init())
            else:
                asyncio.get_event_loop().create_task(self._send_init())
            return

        if line.endswith("NOT OK"):
            _LOGGER.debug("Device NACK: %s", line)
            return

        # Parse firmware version: "cmd uname <version> OK"
        if line.startswith("cmd uname "):
            version_str = line.replace("cmd uname ", "").replace(" OK", "").strip()
            self.firmware_version = version_str
            self.legacy = "V4" in version_str
            _LOGGER.info("Firmware: %s (legacy=%s)", version_str, self.legacy)
            return

        # Parse settings from "cmd set <key> <value> OK" or "cmd get <key> <value> OK"
        if line.startswith("cmd set ") or line.startswith("cmd get ") or line.startswith("get "):
            self._parse_setting(line)
            return

        # Parse telemetry: "tmp <counter> <setpoint> <boiler> <sensor2>"
        if line.startswith("tmp ") or line.startswith("T "):
            self._parse_telemetry(line)
            return

        # Parse PID output: "pid <P> <I> <D> [<extra>]"
        if line.startswith("pid "):
            self._parse_pid(line)
            return

        # Parse shot timer: "sht <x> <millis>"
        if line.startswith("sht "):
            self._parse_shot_timer(line)
            return

    async def _send_init(self) -> None:
        """Send initialization commands after connecting."""
        try:
            # Set clock: seconds since midnight
            now = time.localtime()
            seconds_since_midnight = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
            await self._write(f"\ncmd clock set {seconds_since_midnight}\n")

            # Request firmware version
            await self._write("\ncmd uname OK\n")

            # Dump all settings
            await self._write("\ncmd dump\n")

            self._init_event.set()
        except BleakError as err:
            _LOGGER.error("Failed to send init commands: %s", err)

    def _parse_setting(self, line: str) -> None:
        """Parse a setting response and store the value."""
        # Normalize "get key value" → "cmd get key value"
        if line.startswith("get "):
            line = "cmd " + line

        parts = line.split(" ")
        if len(parts) < 4:
            return

        key = parts[2]

        # Some firmware versions send "pd1imn" instead of "pd1imm" for the
        # PID I wind-down minimum setting (the Android app has the same
        # discrepancy between preference.xml and MainActivity.java).
        if key == "pd1imn":
            key = "pd1imm"

        raw_value = parts[3].replace(".00", "")

        try:
            if key in BOOLEAN_KEYS:
                self.settings[key] = int(float(raw_value)) != 0
            elif key in STRING_KEYS:
                self.settings[key] = raw_value
            else:
                # Store as raw device integer; we scale when reading
                self.settings[key] = int(float(raw_value))
        except (ValueError, TypeError):
            _LOGGER.debug("Could not parse setting %s = %s", key, raw_value)
            return

        # Track dump completion
        if self._awaiting_dump:
            self._dump_keys_received.add(key)

    def _parse_telemetry(self, line: str) -> None:
        """Parse telemetry line: 'tmp <counter> <setpoint> <boiler> <sensor2>'."""
        parts = line.replace("T ", "").replace("tmp ", "").split()
        if len(parts) < 3:
            return

        try:
            # Values are in hundredths of a degree
            setpoint = float(parts[1]) / 100.0
            boiler = float(parts[2]) / 100.0
            self.telemetry["setpoint_temp"] = setpoint
            self.telemetry["boiler_temp"] = boiler

            if len(parts) >= 4:
                second = float(parts[3]) / 100.0
                if 0.05 < second < 200.0:
                    self.telemetry["second_sensor_temp"] = second
                else:
                    self.telemetry["second_sensor_temp"] = None
        except (ValueError, IndexError):
            _LOGGER.debug("Failed to parse telemetry: %s", line)
            return

        if self._on_telemetry_callback is not None:
            self._on_telemetry_callback()

    def _parse_pid(self, line: str) -> None:
        """Parse PID output: 'pid <P> <I> <D> [<extra>]'."""
        parts = line.split()
        if len(parts) < 4:
            return

        try:
            total = sum(int(parts[i]) for i in range(1, min(len(parts), 5)))
            # Convert to percentage: sum / 65535 * 100
            power_pct = total / 65535.0 * 100.0
            self.telemetry["pid_power"] = min(power_pct, 100.0)
        except (ValueError, IndexError):
            _LOGGER.debug("Failed to parse PID: %s", line)
            return

        if self._on_telemetry_callback is not None:
            self._on_telemetry_callback()

    def _parse_shot_timer(self, line: str) -> None:
        """Parse shot timer: 'sht <state> <millis>'.

        When millis == 0, a shot has started — we record the monotonic
        timestamp so the sensor entity can count up in real-time.
        When millis > 0, the shot has ended and millis is the total
        firmware-measured duration.
        """
        parts = line.split()
        if len(parts) < 3:
            return

        try:
            millis = int(parts[2])
            if millis == 0:
                # Shot started
                self.telemetry["shot_timer"] = 0.0
                self.telemetry["shot_timer_active"] = True
                self.telemetry["shot_timer_start"] = time.monotonic()
                self.record_activity()
            else:
                # Shot ended — use firmware-measured duration
                self.telemetry["shot_timer"] = millis / 1000.0
                self.telemetry["shot_timer_active"] = False
                self.record_activity()
        except (ValueError, IndexError):
            _LOGGER.debug("Failed to parse shot timer: %s", line)
            return

        if self._on_telemetry_callback is not None:
            self._on_telemetry_callback()

    def get_scaled_value(self, key: str) -> float | int | bool | str | None:
        """Get a setting value, applying the appropriate scale factor."""
        if key not in self.settings:
            return None

        value = self.settings[key]

        if isinstance(value, bool) or key in BOOLEAN_KEYS:
            return value

        if key in STRING_KEYS:
            return value

        # Apply scale factor
        scale = self._get_scale(key)
        if scale != 1.0:
            return float(value) / scale

        return value

    def encode_value(self, key: str, human_value: float | int | bool | str) -> str:
        """Encode a human-readable value to the device wire format."""
        if key in BOOLEAN_KEYS:
            return "1" if human_value else "0"

        if key in STRING_KEYS:
            return str(human_value)

        scale = self._get_scale(key)
        device_value = int(round(float(human_value) * scale))
        return str(device_value)

    def _get_scale(self, key: str) -> float:
        """Get the scale factor for a key, considering legacy mode."""
        if self.legacy and key in LEGACY_SCALE_FACTORS:
            return LEGACY_SCALE_FACTORS[key]
        return SCALE_FACTORS.get(key, 1.0)

    async def async_set_value(
        self,
        key: str,
        human_value: float | int | bool | str,
        *,
        _internal: bool = False,
    ) -> None:
        """Set a value on the device.

        Raises BleakError if the device is not connected.

        The _internal flag is used by the auto-shutoff sequence to avoid
        resetting the activity timer when it manipulates timer settings.
        """
        if not self.is_connected:
            raise BleakError(
                f"Cannot set {key}: device {self.name} is not connected"
            )

        async with self._operation_lock:
            wire_value = self.encode_value(key, human_value)
            await self._write(f"cmd set {key} {wire_value}\n")

            # Update local cache immediately
            if key in BOOLEAN_KEYS:
                self.settings[key] = bool(human_value)
            elif key in STRING_KEYS:
                self.settings[key] = str(human_value)
            else:
                self.settings[key] = int(round(float(human_value) * self._get_scale(key)))

        if not _internal:
            self.record_activity()

    async def async_request_dump(self) -> None:
        """Request a full settings dump from the device."""
        async with self._operation_lock:
            self._awaiting_dump = True
            self._dump_keys_received.clear()
            self._dump_event.clear()
            await self._write("\ncmd dump\n")

            # Wait for dump to complete (or timeout).
            # The device sends all settings sequentially;
            # we consider the dump complete after no new keys arrive
            # for a short period.
            try:
                prev_count = 0
                for _ in range(30):  # Max 30 × 0.5s = 15s
                    await asyncio.sleep(0.5)
                    current_count = len(self._dump_keys_received)
                    if current_count > 0 and current_count == prev_count:
                        # No new keys for 0.5s — dump is likely complete
                        break
                    prev_count = current_count
            finally:
                self._awaiting_dump = False

    async def async_wait_for_init(self, timeout: float = 20.0) -> bool:
        """Wait for initialization to complete."""
        try:
            await asyncio.wait_for(self._init_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            _LOGGER.warning("Init timeout for %s", self.name)
            return False
