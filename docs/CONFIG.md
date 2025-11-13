# Configuration Options

## Ryobi Credentials

`ryobi_gdo_2_mqtt` requires your Ryobi account credentials to authenticate with the Ryobi API and establish WebSocket connections to your devices.

| CLI | ENV | Purpose |
| --- | --- | --- |
| `--email` | `RYOBI_EMAIL` | The email address you registered with your Ryobi account |
| `--password` | `RYOBI_PASSWORD` | The password you registered for your Ryobi account |

## MQTT Configuration

In order to make your devices appear in Home Assistant, you will need to have configured Home Assistant with an MQTT broker.

- [follow these steps](https://www.home-assistant.io/integrations/mqtt/#configuration)

You will also need to configure `ryobi_gdo_2_mqtt` to use the same broker:

| CLI | ENV | Purpose |
| --- | --- | --- |
| `--mqtt-host` | `RYOBI_MQTT_HOST` | The host name or IP address of your mqtt broker. This should be the same broker that you have configured in Home Assistant. |
| `--mqtt-port` | `RYOBI_MQTT_PORT` | The port number of the mqtt broker. The default is `1883` |
| `--mqtt-user` | `RYOBI_MQTT_USER` | If your broker requires authentication, the username to use |
| `--mqtt-password` | `RYOBI_MQTT_PASSWORD` | If your broker requires authentication, the password to use |

## Logging Configuration

You can control the verbosity of logging output:

| CLI | ENV | Purpose |
| --- | --- | --- |
| `--log-level` | `RYOBI_LOG_LEVEL` | Set the logging level. Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Default is `INFO` |