# Ryobi GDO to MQTT bridge for Home Assistant

This repo provides a `ryobi_gdo_2_mqtt` executable whose primary purpose is to act
as a bridge between [Ryobi](https://www.ryobitools.com/) Garage Door Opener devices and Home Assistant,
via the [Home Assistant MQTT Integration](https://www.home-assistant.io/integrations/mqtt/).

## Features

- Robust WebSocket-based design for real-time status updates
- Support for all Ryobi GDO modules and accessories
- Automatic device discovery
- Live device status updates via WebSocket connection

| Feature              | Notes                                                  |
| -------------------- | ------------------------------------------------------ |
| Garage Door Control  | Open, close, and stop commands with real-time status   |
| Garage Light Control | Turn light on/off                                      |
| Vacation Mode        | Enable/disable vacation mode to prevent door operation |
| Motion Sensor        | Detect motion in garage (if equipped)                  |
| Battery Status       | Monitor backup battery level (if equipped)             |
| WiFi Signal          | Monitor device WiFi signal strength                    |
| Park Assist          | Control park assist laser (if equipped)                |
| Inflator             | Control air compressor/inflator (if equipped)          |
| Bluetooth Speaker    | Control bluetooth speaker (if equipped)                |
| Fan                  | Control fan speed (if equipped)                        |

## Usage

- [Running it in Docker](/docs/DOCKER.md) (Coming Soon)
- [Configuration](/docs/CONFIG.md) (Coming Soon)

## Requirements

- Ryobi Garage Door Opener with WiFi connectivity
- Ryobi account credentials (email and password)
- MQTT broker (e.g., Mosquitto)
- Home Assistant with MQTT integration configured

## Configuration

The application can be configured via environment variables or command-line arguments:

| Variable              | Required | Default | Description                                           |
| --------------------- | -------- | ------- | ----------------------------------------------------- |
| `RYOBI_EMAIL`         | Yes      | -       | Ryobi account email address                           |
| `RYOBI_PASSWORD`      | Yes      | -       | Ryobi account password                                |
| `RYOBI_MQTT_HOST`     | Yes      | -       | MQTT broker hostname or IP                            |
| `RYOBI_MQTT_PORT`     | No       | 1883    | MQTT broker port                                      |
| `RYOBI_MQTT_USER`     | No       | ""      | MQTT username (if required)                           |
| `RYOBI_MQTT_PASSWORD` | No       | ""      | MQTT password (if required)                           |
| `RYOBI_LOG_LEVEL`     | No       | INFO    | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |

## Credits

This work is heavily inspired by [catduckgnaf/ryobi_gdo](https://github.com/catduckgnaf/ryobi_gdo).

## License

MIT License - see LICENSE file for details
