import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,  # Set default level, will be overridden by settings
)

log = logging.getLogger(__name__)

# Also configure logging for ha-mqtt-discoverable
ha_mqtt_log = logging.getLogger("ha_mqtt_discoverable")
paho_log = logging.getLogger("paho.mqtt.client")
