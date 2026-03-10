# meCoffee PID — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration for the meCoffee BLE PID controller for espresso machines. Replaces the original meBarista Android app by exposing all device features as Home Assistant entities.

> **Note:** This integration supports meCoffee PCB **V9 and newer** (modern firmware). The legacy V4 hardware is **not supported**.

## What is meCoffee?

The meCoffee PID is an aftermarket controller for espresso machines that provides precise temperature control, pressure profiling, and advanced shot management. It communicates with external devices using Bluetooth Low Energy (BLE).

For more information about the hardware, visit the official website at [https://mecoffee.nl](https://mecoffee.nl). This integration serves as a complete replacement for the original meBarista Android app, allowing you to automate and monitor your espresso machine directly from Home Assistant.

## Features

- BLE auto-discovery for easy setup
- Real-time sensor updates pushed via BLE notifications (~1/second)
- Real-time monitoring of boiler temperature and PID power output
- Live shot timer that counts up during extraction
- Precise PID tuning and temperature setpoint control
- Full preinfusion control (pump time, pause time, and valve management)
- Pressure profiling with configurable start, end, and period settings
- Automated wake and shutdown scheduling
- Hardware output mapping for pump, boiler, and valve
- Instant reconnection when the machine powers on

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance.
2. Click the three dots in the top right and select "Custom repositories".
3. Add `https://github.com/JakobHP/meCoffee-HA` with the category "Integration".
4. Search for "meCoffee PID" and click install.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/mecoffee/` directory to your Home Assistant `config/custom_components/mecoffee/` directory.
2. Restart Home Assistant.

## Setup

The integration automatically discovers meCoffee devices via Bluetooth. Once your device is powered on and within range, it should appear in your Home Assistant inbox.

You can also add the integration manually:
1. Navigate to Settings → Devices & Services.
2. Click "Add Integration".
3. Search for "meCoffee PID".

Note: This integration requires a functional Bluetooth adapter on your Home Assistant host or a configured Bluetooth proxy.

## Entity Reference

### Sensors

| Entity | Description | Unit |
| :--- | :--- | :--- |
| Boiler temperature | Current real-time boiler temperature | °C |
| Setpoint temperature | Active target temperature from the PID | °C |
| Second sensor temperature | Auxiliary temperature probe (disabled by default) | °C |
| PID power | Current power output to the heater | % |
| Shot timer | Live counting timer during a shot; final firmware-measured duration after | s |
| Firmware version | Device firmware identifier (diagnostic) | — |

### Numbers

#### Temperature
| Entity | Range | Step | Unit |
| :--- | :--- | :--- | :--- |
| Brew temperature | 50 – 125 | 0.5 | °C |
| Steam temperature | 110 – 140 | 0.5 | °C |

#### PID Tuning
| Entity | Range | Step | Unit |
| :--- | :--- | :--- | :--- |
| PID Proportional (P) | 0 – 100 | 1 | — |
| PID Integral (I) | 0 – 1 | 0.01 | — |
| PID Derivative (D) | 0 – 256 | 1 | — |
| PID I wind-down min | 0 – 100 | 1 | % |
| PID I wind-down max | 0 – 100 | 1 | % |
| PID Polling interval | 1000 – 10000 | 500 | ms |

#### Preinfusion
| Entity | Range | Step | Unit |
| :--- | :--- | :--- | :--- |
| Preinfusion pump time | 0 – 10 | 0.1 | s |
| Preinfusion pause time | 0 – 10 | 0.1 | s |

#### Pressure Profiling
| Entity | Range | Step | Unit |
| :--- | :--- | :--- | :--- |
| Pressure start | 0 – 100 | 1 | % |
| Pressure end | 0 – 100 | 1 | % |
| Pressure period | 0 – 60 | 1 | s |

#### Other Settings
| Entity | Range | Step | Unit |
| :--- | :--- | :--- | :--- |
| Pro-active heating | 0 – 100 | 1 | % |
| Max shot time | 0 – 60 | 1 | s |
| Auto shutoff | 0 – 120 | 1 | min |

### Switches

| Entity | Description |
| :--- | :--- |
| Continuous mode | Switches between interval (SSR relay) and continuous (dimmer) boiler heating |
| Preinfusion | Enables the preinfusion cycle for shots |
| Preinfusion close valve | Closes the valve during the preinfusion pause phase |
| Wake timer | Enables the automatic scheduled wake-up |
| Shutdown timer | Enables the automatic scheduled shutdown |
| Timer power mode | Allows the timer to control the power relay directly |
| Power button flip | Inverts the logic of the physical power button |

### Selects

| Entity | Description | Options |
| :--- | :--- | :--- |
| Output 0 assignment | Hardware mapping for output 0 | Pump, Boiler, Valve, Indicator, Grinder, Disabled |
| Output 1 assignment | Hardware mapping for output 1 | Pump, Boiler, Valve, Indicator, Grinder, Disabled |
| Output 2 assignment | Hardware mapping for output 2 | Pump, Boiler, Valve, Indicator, Grinder, Disabled |

### Time

| Entity | Description |
| :--- | :--- |
| Wake-up time | The scheduled time of day for the machine to wake up |
| Shutdown time | The scheduled time of day for the machine to shut down |

## Connection Behavior

The meCoffee PID controller is physically attached to an espresso machine that is frequently powered off. The integration is designed to handle this gracefully — no manual intervention is needed when the machine is turned on or off.

### When the machine is powered off

1. The BLE link drops. The integration detects this immediately via a disconnect callback.
2. All sensor entities (temperature, PID power, shot timer) go to **unavailable** within seconds.
3. Settings entities (numbers, switches, selects, times) retain their last-known values but show as **unavailable** after the next poll cycle fails.
4. Attempting to change a setting while the device is off will show an error notification in the HA UI ("Failed to set …: device is not connected").

### Reconnection

The integration automatically retries the connection on every coordinator poll cycle, with **exponential back-off** to avoid unnecessary Bluetooth traffic:

| Consecutive failures | Retry interval |
| :--- | :--- |
| 1 | 10 seconds |
| 2 | 30 seconds |
| 3 | 1 minute |
| 4 | 2 minutes |
| 5+ | 5 minutes |

### When the machine is powered back on

1. The BLE module starts advertising again.
2. The integration detects the advertisement **immediately** via a registered Bluetooth callback, resets the reconnection backoff to zero, and triggers an instant coordinator refresh.
3. Within seconds, the integration connects, sends the initialization sequence (clock sync, firmware version query, settings dump), and resumes telemetry streaming.
4. All entities become **available** again with live data.

No restart of Home Assistant or the integration is required. You will typically see live data within a few seconds of flipping the power switch.

### Auto-shutoff (local enforcement)

The meCoffee firmware has a built-in inactivity timer (`tmrosd`) that is supposed to shut off the machine after a configurable number of idle minutes. However, **the firmware counts an active BLE connection as activity**, which means the timer never fires while this integration (or the meBarista app) is connected — the machine stays on indefinitely.

This integration works around the problem by **enforcing the auto-shutoff locally**. It tracks real user activity — shots pulled, settings changed — and ignores passive telemetry. When idle time exceeds the configured `tmrosd` value, the integration triggers a shutdown using the firmware's scheduled-shutdown timer:

1. The current shutdown-time and shutdown-enable settings are saved.
2. A shutdown time is set to the next whole minute.
3. The shutdown timer is enabled.
4. The integration polls PID power output until it drops to 0% (confirming the firmware shut off the boiler), with a 90-second hard timeout.
5. The original shutdown timer settings are restored.

If the device disconnects during the sequence (e.g., the firmware also powers off the BLE module), the saved settings are restored automatically on the next reconnect.

**No configuration is needed.** If `tmrosd` (Auto Shutoff) is set to a non-zero value, the local enforcement is active automatically. Set it to 0 to disable auto-shutoff entirely.

## Troubleshooting

- **Device not found**: Check that the meCoffee PID is powered on and within Bluetooth range. Ensure it is not currently connected to the meBarista app or another Bluetooth client. Only one BLE central can connect to the HM-10 module at a time.
- **Entities stuck as unavailable**: Check the Home Assistant log for `meCoffee` entries. Common causes: the machine is off (expected), the Bluetooth adapter is not working, or another client has the connection. The integration will reconnect automatically once the device is available.
- **Settings not updating**: The integration reads all settings via a command dump upon initial connection. Telemetry (temperature, PID output, shot timer) is streamed in real-time while connected. If settings appear out of sync, try reloading the integration from Settings → Devices & Services.
- **"Failed to set …" errors**: This means you tried to change a setting while the device is off or out of range. Wait for the machine to power on and the entities to become available before making changes.
- **Frequent disconnects while the machine is on**: Bluetooth signal strength may be insufficient. Consider using an [ESPHome Bluetooth Proxy](https://esphome.io/components/bluetooth_proxy.html) placed closer to the espresso machine.

## In-Depth Entity Guide

This section provides detailed explanations of every entity in the integration, including what each setting controls physically on the espresso machine and how the firmware interprets the values.

### How the meCoffee Works Physically

The meCoffee is a small PCB (ATmega328PU microcontroller + BLE module) installed inside an espresso machine. It physically takes over control of three components:

1. **Boiler heater** — via an internal SSR (solid-state relay) or TRIAC dimmer. The factory thermostat is bypassed; the meCoffee's own temperature sensor (LM35DT) sits in the boiler's steam thermostat hole.
2. **Pump** — via a relay/TRIAC that can cut power to the vibratory pump mid-shot (for preinfusion) or dim it (for pressure profiling).
3. **3-way solenoid valve** — can be independently opened/closed during preinfusion to trap or release pressure in the brew path.

All settings are sent over BLE as newline-delimited text commands: `cmd set <key> <value>\n`. The integration handles this identically to the original meBarista Android app.

**Supported machines**: Primarily the Rancilio Silvia (V1–V5/E), Gaggia Classic, and Vibiemme Domobar, though the meCoffee can be wired into most single-boiler espresso machines with a vibratory pump.

---

### Sensors

#### Boiler Temperature
- **Protocol line**: `tmp <counter> <setpoint> <boiler_temp> <sensor2_temp>` — `boiler_temp ÷ 100` = °C
- The live temperature of the boiler body, read from the LM35DT sensor. This is the PID's **process variable** — what the controller is trying to match to the setpoint. Updates approximately once per second while connected. During a shot, you'll see a dip as cold reservoir water enters the boiler, followed by recovery as the PID and pro-active heating react.

#### Setpoint Temperature
- **Protocol line**: Same `tmp` line, second field.
- The *active* target temperature the firmware's PID loop is currently targeting. Normally equals your **Brew Temperature** setting, but automatically switches to the **Steam Temperature** value when the machine's physical steam switch is activated (handled by the firmware, not the app). Useful for confirming the firmware is in the correct mode.

#### Second Sensor Temperature
- **Protocol line**: Same `tmp` line, fourth field. Only shown when the value is between 0.05 °C and 200 °C (plausible reading from a connected sensor).
- A second temperature probe, typically mounted on the **group head** — the heavy brass fitting the portafilter locks into. The group head temperature lags behind the boiler by several minutes, so this sensor tells you when the machine is *truly* warmed up for brewing (not just the boiler). If no second sensor is physically installed, this entity will read zero or be unavailable.

#### PID Power
- **Protocol line**: `pid <P> <I> <D> [<extra>]` — `(P + I + D + extra) / 65535 × 100` = %
- The current percentage of power being applied to the boiler heater. Displays **0%** on connect until the first `pid` line arrives (never "Unknown"). The four terms (Proportional, Integral, Derivative, and an optional feed-forward offset) are summed and normalized against the 16-bit PWM maximum (65535 = 0xFFFF = 100%). At idle near setpoint you'll see ~5–20%. During warm-up: 100%. During a shot, it spikes as the pro-active boost kicks in.

#### Shot Timer
- **Protocol line**: `sht <state> <millis>` — `millis ÷ 1000` = seconds
- Displays **0** when idle (never "Unknown"). When a shot starts, the entity counts up in real-time at 1-second resolution using a client-side timer. When the shot ends, it locks to the firmware-reported duration. If preinfusion is enabled, the total time includes the preinfusion pause — the Android app subtracts the pause to show "effective extraction time," but this integration reports the full duration.

#### Firmware Version
- **Protocol line**: Response to `cmd uname OK` — e.g. `meCoffee pcb V9 30 149 12`
- The device's hardware board version and firmware build identifier. Displayed as a diagnostic string. The format is: `meCoffee pcb <board_version> <build_number> <day_of_year> <sub_version>`.

---

### Number Entities

#### Brew Temperature (`tmpsp`)
- **Range**: 50–125 °C, step 0.5 °C — **Default**: 101 °C
- **Wire format**: value × 100 (centidegrees). 93.5 °C → `cmd set tmpsp 9350`

Sets the PID target temperature for brewing. The firmware continuously compares this to the boiler sensor reading and adjusts heater output. This is the single most important setting — it directly determines your espresso extraction temperature. Typical espresso range is 90–96 °C at the group head, though you may need to set the boiler higher to account for thermal loss between boiler and group.

#### Steam Temperature (`tmpstm`)
- **Range**: 110–140 °C, step 0.5 °C — **Default**: 125 °C
- **Wire format**: value × 100

Sets the PID target when the machine's physical steam switch is activated. The firmware automatically switches between brew and steam setpoints — no app interaction needed. The range caps at 140 °C because the LM35DT sensor's maximum operating temperature is ~150 °C; the 140 °C limit provides a safety margin while still generating adequate steam pressure for milk frothing.

#### PID Proportional — P (`pd1p`)
- **Range**: 0–100, step 1 — **Default**: 20
- **Wire format**: sent as-is

Controls how aggressively the heater reacts to the *current* temperature error (the gap between setpoint and actual boiler temperature). Higher P means faster response but risks oscillation. The P-term's contribution to heater output is proportional to the error magnitude — if the boiler is 5 °C below setpoint with P=20, the P-term contributes a proportionally larger share of the 65535-max output.

#### PID Integral — I (`pd1i`)
- **Range**: 0–1.00, step 0.01 — **Default**: 0.30
- **Wire format**: value × 100. Display 0.30 → `cmd set pd1i 30`

Eliminates steady-state offset. The I-term accumulates error over time — if the temperature sits consistently 0.2 °C below setpoint, the integral slowly increases heater output until the gap closes. Too high a value causes overshoot and oscillation; too low means the machine never quite reaches setpoint. The ×100 scale gives fine-grained control: 0.01 increments in the UI correspond to integer steps on the firmware.

#### PID Derivative — D (`pd1d`)
- **Range**: 0–256, step 1 — **Default**: 128
- **Wire format**: sent as-is

Dampens oscillation by reacting to the *rate of change* of temperature. If the temperature is rising rapidly toward setpoint, the D-term reduces heater output *before* setpoint is reached, preventing overshoot. Think of it as the "brakes." Higher D means more damping. The 0–256 range maps to an 8-bit value on the firmware.

#### PID I Wind-Down Min (`pd1imm`)
- **Range**: 0–100%, step 1 — **Default**: 0%
- **Wire format**: value × 655.36 (65536 ÷ 100, mapping 0–100% to the 16-bit PWM range)

Sets the **floor** of the integral term's steady-state contribution. At 0% (default), the integral can wind all the way down to zero — the PID provides no guaranteed "maintenance heat" via the I-term when at setpoint. Setting this to, say, 5% means the I-term always contributes at least 5% heater power even when the boiler is exactly at setpoint. This prevents the boiler from cooling between shots on machines with high thermal loss, but risks mild oscillation.

#### PID I Wind-Down Max (`pd1imx`)
- **Range**: 0–100%, step 1 — **Default**: 20%
- **Wire format**: value × 655.36

Sets the **ceiling** of the integral term's contribution — the **anti-windup limit**. This is the most important PID safety setting. During cold startup, the temperature error is huge (e.g., 20 °C → target). Without a ceiling, the I-term accumulates an enormous value during warmup. When the boiler finally reaches setpoint, that accumulated integral keeps commanding near-100% heat, causing a **massive overshoot** — potentially +5–10 °C, which means scalded coffee. At 20% (default), the I-term can never contribute more than 20% of full heater power, keeping overshoot manageable. The meCoffee docs suggest values of 3000–4000 in raw units (roughly 5–6%) for tighter control.

#### PID Polling Interval (`pd1sz`)
- **Range**: 1000–10000 ms, step 500 ms — **Default**: 1000 ms
- **Wire format**: sent as-is (milliseconds)

How often the firmware executes its PID loop — read sensor, compute error, update heater output. The correct value depends on **Continuous Mode**:
- **Continuous mode ON** (TRIAC dimmer): Use **1000 ms**. The dimmer can change power smoothly every second.
- **Continuous mode OFF** (SSR interval switching): Use **5000 ms**. The relay needs a full on/off cycle per period. Too short a period causes mechanical relay wear, audible clicking, and EMI issues.

#### Preinfusion Pump Time (`pistrt`)
- **Range**: 0–10 s, step 0.1 s — **Default**: 3.0 s
- **Wire format**: value × 1000 (milliseconds). 3.0 s → `cmd set pistrt 3000`

When preinfusion is enabled and you start a shot, the pump runs for this many seconds first. Water flows into the group head at relatively low pressure (the system isn't fully sealed yet), wetting the top of the coffee puck. This initial wetting prevents **channeling** — water blasting through cracks in dry grounds rather than saturating them evenly. After this time, the pump stops for the pause phase.

#### Preinfusion Pause Time (`piprd`)
- **Range**: 0–10 s, step 0.1 s — **Default**: 3.0 s
- **Wire format**: value × 1000 (milliseconds)

After the pump phase, the pump stops for this duration. The already-wet grounds continue to absorb water and swell ("bloom"), filling gaps in the puck and mechanically sealing against the basket walls. The meCoffee documentation calls this "welding" the puck. After the pause, the pump restarts at full pressure for normal extraction.

#### Pressure Start (`pp1`)
- **Range**: 0–100%, step 1 — **Default**: 100%
- **Wire format**: sent as-is

The pump power at the **beginning** of a shot. This is a PWM duty cycle for the vibratory pump — the meCoffee's TRIAC dims the AC power to the pump, causing it to run slower and build less pressure. At 100%, the pump delivers full ~9 bar pressure. At lower values, proportionally less. This allows you to start a shot gently (low-pressure pre-wetting) then ramp up, or vice versa.

#### Pressure End (`pp2`)
- **Range**: 0–100%, step 1 — **Default**: 100%
- **Wire format**: sent as-is

The pump power at the **end** of the profiling period. The firmware linearly ramps from the start percentage to this value over the pressure period. After the period elapses, power stays at this value for the rest of the shot.

**Example profiles**:
| Start | End | Period | Effect |
|:---:|:---:|:---:|:---|
| 100% | 100% | 25 s | No profiling — flat full pressure (default) |
| 100% | 70% | 25 s | Classic "declining" profile for a gentler extraction finish |
| 50% | 100% | 10 s | "Rising" profile — starts soft, ramps to full (good for blooming) |
| 80% | 80% | 25 s | Fixed reduced pressure (useful for machines with over-9-bar pumps) |

#### Pressure Period (`ppt`)
- **Range**: 0–60 s, step 1 — **Default**: 25 s
- **Wire format**: sent as-is (seconds)

The time over which the pump power linearly ramps from the start to end percentage. The meBarista app describes this as: *"the period to taper from the start pressure to the end pressure."* If your shot is shorter than this period, you'll only use the first portion of the ramp.

#### Pro-Active Heating (`tmppap`)
- **Range**: 0–100%, step 1 — **Default**: 33%
- **Wire format**: sent as-is

A **feed-forward boost**. The instant the firmware detects the brew button being pressed (via the Active PID sense wire), it immediately adds this percentage of extra heater power *before* the temperature sensor even registers a drop. Cold reservoir water entering the boiler during a shot causes a temperature dip of 5–15 °C on a typical Silvia. The PID reacts, but it's slow — thermal mass introduces significant lag. Pro-active heating compensates pre-emptively. At 33% (default), the heater gets an instant 33% power boost the moment your shot starts. At 0%, the PID alone reacts (with a lag).

#### Max Shot Time (`shtmx`)
- **Range**: 0–60 s, step 1 — **Default**: 60 s
- **Wire format**: sent as-is (seconds)

A safety limit — when the shot reaches this duration, the firmware cuts the pump. Prevents accidentally running water through the puck indefinitely if you walk away. Setting to **0 disables the limit** entirely (infinite shot time). Despite appearing in the Preinfusion settings screen in the Android app, this setting is functionally independent of preinfusion.

#### Auto Shutoff (`tmrosd`)
- **Range**: 0–120 min, step 1 — **Default**: 60 min
- **Wire format**: sent as-is (minutes)

An **inactivity timer**. If the machine sits idle (no shots pulled, no settings changed) for this many minutes, the machine shuts off. Setting to 0 disables the timer. This is independent of both the scheduled shutdown timer and continuous mode — `tmrosd` is a complete machine shutdown trigger based on inactivity, while `tmpcntns` only affects how the boiler heater is driven.

> **Note:** The firmware's built-in `tmrosd` timer does not work while a BLE client is connected (it treats the connection itself as activity). This integration enforces the timer locally by tracking real user activity and triggering a shutdown via the firmware's scheduled-shutdown mechanism when the idle period is exceeded. See [Auto-shutoff (local enforcement)](#auto-shutoff-local-enforcement) for details.

---

### Switch Entities

#### Continuous Mode (`tmpcntns`)
- **Default**: OFF

Switches between two boiler heating strategies:
- **OFF (interval / SSR mode)**: The heater relay clicks fully ON for a fraction of each PID window, then fully OFF. For example, at 60% output with a 5-second window: 3 s on, 2 s off. Audible clicking. Causes slight temperature ripple.
- **ON (continuous / dimmer mode)**: A TRIAC phase-cuts the AC waveform — like a light dimmer. At 60% output, the heater receives 60% power continuously. Smoother temperature control, silent operation, and enables shorter PID polling intervals (1000 ms vs 5000 ms).

This switch does **not** affect auto-shutoff or prevent the machine from turning off. It only changes *how* electrical power is delivered to the heating element.

#### Preinfusion (`pinbl`)
- **Default**: OFF

Master toggle for the preinfusion cycle. When ON, every shot goes through a three-phase sequence:
1. **Pump phase** — pump runs for the configured pump time, gently wetting the puck.
2. **Pause phase** — pump stops for the configured pause time; the puck absorbs water and swells.
3. **Extraction** — pump restarts at full pressure for normal espresso extraction.

When OFF, the pump runs continuously from the moment you press the brew button. Requires the pump and valve to be wired through the meCoffee.

#### Preinfusion Close Valve (`pivlv`)
- **Default**: OFF

Controls the 3-way solenoid valve during the preinfusion pause phase:
- **OFF**: The valve stays open during the pause. Residual pressure from the pump phase bleeds off slowly. The puck is wet but not under active pressure.
- **ON**: The valve closes, **trapping** the pressure built up during the pump phase inside the portafilter. The puck continues to soak under trapped pressure, producing more uniform wetting — especially with fine grinds. The tradeoff: if the initial pump phase didn't wet the puck evenly, the closed valve can lock in channeling.

#### Wake Timer (`tmrwnbl`)
- **Default**: OFF

Enables the automatic scheduled wake-up. When ON, the firmware monitors its internal clock (synced from Home Assistant via BLE on each connection) and powers on the machine at the time set in **Wake-Up Time**. Useful for having your machine pre-heated and ready when you wake up.

#### Shutdown Timer (`tmrsnbl`)
- **Default**: OFF

Enables automatic scheduled shutdown at the absolute time of day set in **Shutdown Time**. This is independent of the inactivity-based Auto Shutoff timer — you can use both simultaneously.

#### Timer Power Mode (`tmrpwr`)
- **Default**: OFF

An installation mode flag for machines where the meCoffee controls the power relay — meaning the machine is always receiving mains power and the meCoffee decides when it's "on." When enabled, the firmware **does not begin warming up on cold boot or after a power outage**. It waits for either a scheduled wake event or a manual turn-on command. Without this, plugging the machine in or recovering from a power outage would immediately start heating the boiler. The firmware summary: *"Prevent warmup after power outage or cold boot."*

#### Power Button Flip (`pwrflp`)
- **Default**: OFF

Accommodates different physical power switch types:
- **OFF**: The firmware expects a **latching toggle** switch — stays in one position when pressed (common on Silvia V1–V4, Gaggia Classic).
- **ON**: The firmware expects a **momentary / rocker button** that springs back after pressing (Rancilio Silvia V5/E and similar). Each button press generates a brief pulse; the firmware treats it as an edge-trigger to toggle the machine on or off. Without this setting enabled, a momentary button would immediately flip back to the previous state.

---

### Select Entities

#### Output 1 / 2 / 3 Assignment (`o0`, `o1`, `o2`)
- **Options**: Pump, Boiler, Valve, Indicator, Grinder, Disabled
- **Defaults**: Output 1 = Pump, Output 2 = Boiler, Output 3 = Valve
- **Wire format**: ASCII decimal code of the function character. `112` = `'p'` = Pump.

The meCoffee PCB has three physical output terminals. These selects let you remap which firmware function drives which physical output. This is necessary because different espresso machine models have their components wired differently.

| Option | ASCII code | Character | Physical function |
|:---|:---:|:---:|:---|
| Pump | 112 | `p` | Vibratory pump (creates brew pressure) |
| Boiler | 98 | `b` | Boiler heating element (via SSR/TRIAC) |
| Valve | 118 | `v` | 3-way solenoid valve (brew path control) |
| Indicator | 105 | `i` | Pilot light or status LED |
| Grinder | 103 | `g` | Integrated grinder relay |
| Disabled | 110 | `n` | Output not driven — use when the machine lacks the component |

---

### Time Entities

#### Wake-Up Time (`tmron`)
- **Default**: 00:00 (midnight)
- **Wire format**: seconds since midnight. 7:30 AM → `cmd set tmron 27000`

The time of day the firmware will automatically power on the machine (if the Wake Timer switch is enabled). Only hour and minute precision — seconds are always zero. The firmware's internal clock is synced from Home Assistant via BLE every time the integration connects.

#### Shutdown Time (`tmroff`)
- **Default**: 00:00 (midnight)
- **Wire format**: seconds since midnight

The time of day the firmware will automatically shut down the machine (if the Shutdown Timer switch is enabled). Same encoding and precision as the wake-up time. Independent of the inactivity-based Auto Shutoff timer.

---

### BLE Protocol Summary

The meCoffee uses a single BLE characteristic (`0000ffe1-...`) for both TX and RX — a serial-over-BLE interface via an HM-10/CC2541 module. Communication is newline-delimited text.

| Direction | Format | Purpose |
|:---|:---|:---|
| Device → Host | `tmp <counter> <sp×100> <boiler×100> <sensor2×100>` | Temperature telemetry (~1/s) |
| Device → Host | `pid <P> <I> <D> [<extra>]` | PID output components |
| Device → Host | `sht <state> <millis>` | Shot timer events |
| Device → Host | `cmd uname <version_string> OK` | Firmware version |
| Device → Host | `cmd get <key> <value> OK` | Setting value response |
| Host → Device | `cmd set <key> <value>\n` | Change a setting |
| Host → Device | `cmd dump\n` | Request all settings |
| Host → Device | `cmd clock set <seconds_since_midnight>\n` | Sync clock |
| Host → Device | `cmd uname OK\n` | Request firmware version |

## Credits

- Built for the meCoffee PID controller ([https://mecoffee.nl](https://mecoffee.nl)).
- Protocol reverse-engineered from the meBarista Android app ([https://git.mecoffee.nl/meBarista/meBarista_for_Android](https://git.mecoffee.nl/meBarista/meBarista_for_Android)).

## License

See [LICENSE](LICENSE) for details.
