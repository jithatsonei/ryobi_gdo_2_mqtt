# Running ryobi_gdo_2_mqtt in Docker

To deploy in docker:

1. Ensure that you have configured the MQTT integration in Home Assistant.

   - [follow these steps](https://www.home-assistant.io/integrations/mqtt/#configuration)
2. Set up a `.env` file. Here's a skeleton file; you will need to populate
   the values with things that make sense in your environment.
   See [CONFIG.md](/docs/CONFIG.md) for more details.

```
# Required: Your Ryobi account credentials
RYOBI_EMAIL=user@example.com
RYOBI_PASSWORD=secret

# Required: MQTT broker connection details
RYOBI_MQTT_HOST=mqtt
RYOBI_MQTT_PORT=1883
# Uncomment if your mqtt broker requires authentication
#RYOBI_MQTT_USER=user
#RYOBI_MQTT_PASSWORD=password

# Optional: Set the log level for debugging
# Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
RYOBI_LOG_LEVEL=INFO

```

3. Set up your `docker-compose.yml`:

```yaml
name: ryobi_gdo_2_mqtt
services:
  ryobi_gdo_2_mqtt:
    image: usethefork/ryobi_gdo_2_mqtt:latest
    container_name: ryobi_gdo_2_mqtt
    restart: unless-stopped
    env_file:
      - .env
    network_mode: bridge
```

4. Launch it:

```
$ docker compose up -d
```

5. If you need to review the logs:

```
$ docker logs ryobi_gdo_2_mqtt --follow
```
