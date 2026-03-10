"""Constants for the meCoffee PID integration."""

from __future__ import annotations

DOMAIN = "mecoffee"

# BLE identifiers
MECOFFEE_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
MECOFFEE_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
MECOFFEE_DEVICE_NAME_PREFIX = "meCoffee"

# Platforms to set up
PLATFORMS: list[str] = [
    "sensor",
    "number",
    "switch",
    "select",
    "time",
]

# Connection
DEFAULT_SCAN_INTERVAL = 10  # seconds between polls
DISCONNECT_DELAY = 60  # seconds before disconnecting after last update

# ── Protocol command keys ──────────────────────────────────────────────
# These map 1:1 to the meCoffee firmware "cmd set/get <key> <value>" keys.
# The Android app prefixes them with "pref_" in SharedPreferences, but we
# store and send them without the prefix.

# Temperature
KEY_BREW_TEMP = "tmpsp"
KEY_STEAM_TEMP = "tmpstm"
KEY_CONTINUOUS_MODE = "tmpcntns"
KEY_PROACTIVE_PCT = "tmppap"

# PID tuning
KEY_PID_P = "pd1p"
KEY_PID_I = "pd1i"
KEY_PID_D = "pd1d"
KEY_PID_I_MIN = "pd1imm"
KEY_PID_I_MAX = "pd1imx"
KEY_PID_INTERVAL = "pd1sz"

# Pressure profiling
KEY_PRESSURE_START = "pp1"
KEY_PRESSURE_END = "pp2"
KEY_PRESSURE_PERIOD = "ppt"

# Preinfusion
KEY_PREINFUSION_ENABLE = "pinbl"
KEY_PREINFUSION_PUMP_TIME = "pistrt"
KEY_PREINFUSION_PAUSE_TIME = "piprd"
KEY_PREINFUSION_CLOSE_VALVE = "pivlv"
KEY_MAX_SHOT_TIME = "shtmx"

# Timers
KEY_AUTO_SHUTOFF = "tmrosd"
KEY_WAKE_ENABLE = "tmrwnbl"
KEY_WAKE_TIME = "tmron"
KEY_SHUTDOWN_ENABLE = "tmrsnbl"
KEY_SHUTDOWN_TIME = "tmroff"

# Hardware
KEY_OUTPUT_0 = "o0"
KEY_OUTPUT_1 = "o1"
KEY_OUTPUT_2 = "o2"
KEY_TIMER_POWER = "tmrpwr"
KEY_POWER_FLIP = "pwrflp"

# ── Scale factors ──────────────────────────────────────────────────────
# When the device stores a value, it multiplies the human-readable value
# by this factor.  On read we divide, on write we multiply.
# e.g. 101.00 °C is stored as 10100 on the device.
SCALE_FACTORS: dict[str, float] = {
    KEY_BREW_TEMP: 100.0,       # °C × 100
    KEY_STEAM_TEMP: 100.0,      # °C × 100
    KEY_PID_I: 100.0,           # I × 100
    KEY_PID_I_MIN: 655.36,      # % × 655.36 (65536 / 100)
    KEY_PID_I_MAX: 655.36,      # % × 655.36
    KEY_PREINFUSION_PUMP_TIME: 1000.0,  # seconds × 1000
    KEY_PREINFUSION_PAUSE_TIME: 1000.0,  # seconds × 1000
}

# Legacy (V4) firmware uses different scales for some keys.
# Only preinfusion times differ: V4 stores them as plain seconds (no ×1000).
LEGACY_SCALE_FACTORS: dict[str, float] = {
    KEY_PREINFUSION_PUMP_TIME: 1.0,
    KEY_PREINFUSION_PAUSE_TIME: 1.0,
}

# ── Default values (human-readable) ───────────────────────────────────
DEFAULTS: dict[str, float | int | bool | str] = {
    KEY_BREW_TEMP: 101.0,
    KEY_STEAM_TEMP: 125.0,
    KEY_CONTINUOUS_MODE: False,
    KEY_PROACTIVE_PCT: 33,
    KEY_PID_P: 20,
    KEY_PID_I: 0.3,
    KEY_PID_D: 128,
    KEY_PID_I_MIN: 0,
    KEY_PID_I_MAX: 20,
    KEY_PID_INTERVAL: 1000,
    KEY_PRESSURE_START: 100,
    KEY_PRESSURE_END: 100,
    KEY_PRESSURE_PERIOD: 25,
    KEY_PREINFUSION_ENABLE: True,
    KEY_PREINFUSION_PUMP_TIME: 3.0,
    KEY_PREINFUSION_PAUSE_TIME: 3.0,
    KEY_PREINFUSION_CLOSE_VALVE: False,
    KEY_MAX_SHOT_TIME: 60,
    KEY_AUTO_SHUTOFF: 60,
    KEY_WAKE_ENABLE: False,
    KEY_WAKE_TIME: 0,
    KEY_SHUTDOWN_ENABLE: False,
    KEY_SHUTDOWN_TIME: 0,
    KEY_OUTPUT_0: "112",  # Pump (ASCII 'p')
    KEY_OUTPUT_1: "98",   # Boiler (ASCII 'b')
    KEY_OUTPUT_2: "118",  # Valve (ASCII 'v')
    KEY_TIMER_POWER: False,
    KEY_POWER_FLIP: False,
}

# ── Output mapping labels ─────────────────────────────────────────────
# Device stores output assignment as ASCII char codes.
OUTPUT_OPTIONS: dict[str, str] = {
    "112": "Pump",       # 'p'
    "98": "Boiler",      # 'b'
    "118": "Valve",      # 'v'
    "105": "Indicator",  # 'i'
    "103": "Grinder",    # 'g'
    "110": "Disabled",   # 'n'
}

# ── Boolean keys ───────────────────────────────────────────────────────
# Keys that are boolean on the device (0/1 integer on wire).
BOOLEAN_KEYS: set[str] = {
    KEY_CONTINUOUS_MODE,
    KEY_PREINFUSION_ENABLE,
    KEY_PREINFUSION_CLOSE_VALVE,
    KEY_WAKE_ENABLE,
    KEY_SHUTDOWN_ENABLE,
    KEY_TIMER_POWER,
    KEY_POWER_FLIP,
}

# ── Integer keys (no scaling, stored as-is) ────────────────────────────
INTEGER_KEYS: set[str] = {
    KEY_PROACTIVE_PCT,
    KEY_PID_P,
    KEY_PID_D,
    KEY_PID_INTERVAL,
    KEY_PRESSURE_START,
    KEY_PRESSURE_END,
    KEY_PRESSURE_PERIOD,
    KEY_MAX_SHOT_TIME,
    KEY_AUTO_SHUTOFF,
    KEY_WAKE_TIME,
    KEY_SHUTDOWN_TIME,
}

# ── String keys ────────────────────────────────────────────────────────
STRING_KEYS: set[str] = {
    KEY_OUTPUT_0,
    KEY_OUTPUT_1,
    KEY_OUTPUT_2,
}
