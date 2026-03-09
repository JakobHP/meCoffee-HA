# meCoffee PID — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration for the meCoffee BLE PID controller for espresso machines. Replaces the original meBarista Android app by exposing all device features as Home Assistant entities.

## What is meCoffee?

The meCoffee PID is an aftermarket controller for espresso machines that provides precise temperature control, pressure profiling, and advanced shot management. It communicates with external devices using Bluetooth Low Energy (BLE).

For more information about the hardware, visit the official website at [https://mecoffee.nl](https://mecoffee.nl). This integration serves as a complete replacement for the original meBarista Android app, allowing you to automate and monitor your espresso machine directly from Home Assistant.

## Features

- BLE auto-discovery for easy setup
- Real-time monitoring of boiler temperature and PID power output
- Precise PID tuning and temperature setpoint control
- Integrated shot timer
- Full preinfusion control (pump time, pause time, and valve management)
- Pressure profiling with configurable start, end, and period settings
- Automated wake and shutdown scheduling
- Hardware output mapping for pump, boiler, and valve
- Support for both modern and legacy V4 firmware versions

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
| Shot timer | Duration of the most recent or active shot | s |
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
| Continuous mode | Keeps the boiler at target temperature without timeout |
| Preinfusion | Enables the preinfusion cycle for shots |
| Preinfusion close valve | Closes the valve during the preinfusion pause phase |
| Wake timer | Enables the automatic scheduled wake-up |
| Shutdown timer | Enables the automatic scheduled shutdown |
| Timer power mode | Allows the timer to control the power relay directly |
| Power button flip | Inverts the logic of the physical power button |

### Selects

| Entity | Description | Options |
| :--- | :--- | :--- |
| Output 0 assignment | Hardware mapping for output 0 | Pump, Boiler, Valve, Disabled |
| Output 1 assignment | Hardware mapping for output 1 | Pump, Boiler, Valve, Disabled |
| Output 2 assignment | Hardware mapping for output 2 | Pump, Boiler, Valve, Disabled |

### Time

| Entity | Description |
| :--- | :--- |
| Wake-up time | The scheduled time of day for the machine to wake up |
| Shutdown time | The scheduled time of day for the machine to shut down |

## Troubleshooting

- **Device not found**: Check that the meCoffee PID is powered on and within Bluetooth range. Ensure it is not currently connected to the meBarista app or another Bluetooth client.
- **Connection drops**: Bluetooth signal stability can vary. Consider using a Bluetooth proxy if the distance between your host and the machine is significant. Check the standard Home Assistant Bluetooth integration logs for adapter issues.
- **Settings not updating**: The integration reads settings via a command dump upon initial connection. Telemetry (temperature, timer) is streamed in real-time while connected. If settings appear out of sync, try toggling the entity or restarting the integration.

## Credits

- Built for the meCoffee PID controller ([https://mecoffee.nl](https://mecoffee.nl)).
- Protocol reverse-engineered from the meBarista Android app ([https://git.mecoffee.nl/meBarista/meBarista_for_Android](https://git.mecoffee.nl/meBarista/meBarista_for_Android)).

## License

See [LICENSE](LICENSE) for details.
