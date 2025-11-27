# Home Assistant add-on

The repository ships a Home Assistant add-on that packages the repo for HAOS installations

## Installation

1. In Home Assistant, open **Settings → Add-ons → Add-on Store**.
2. Click the three dots menu → **Repositories** and add `https://github.com/jithatsonei/ryobi_gdo_2_mqtt`.
3. Install **Ryobi GDO to MQTT Bridge** from the list.
4. Open the add-on, set the options, then **Start**. Check the logs to confirm it connected to MQTT and your Ryobi account.

If images are not yet published for your architecture, Home Assistant will build the add-on locally using the included `addon/Dockerfile`.

## Configuration

| Option          | Default | Notes |
| --------------- | ------- | ----- |
| `ryobi_email`   | -       | Required. Ryobi account email address. |
| `ryobi_password`| -       | Required. Ryobi account password. |
| `mqtt_host`     | ""      | MQTT broker host. Leave blank to use the Home Assistant MQTT integration values. |
| `mqtt_port`     | 1883    | MQTT broker port. |
| `mqtt_username` | ""      | MQTT username if your broker requires it. |
| `mqtt_password` | ""      | MQTT password if your broker requires it. |
| `log_level`     | INFO    | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

The add-on will automatically pull MQTT host/port/user/password from the Home Assistant MQTT integration if it is configured and the explicit options are left blank.
