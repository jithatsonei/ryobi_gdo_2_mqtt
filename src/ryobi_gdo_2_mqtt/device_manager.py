import asyncio

from ha_mqtt_discoverable import DeviceInfo, Settings as MQTTSettings
from ha_mqtt_discoverable.sensors import BinarySensor, BinarySensorInfo, Cover, CoverInfo, Switch, SwitchInfo
from paho.mqtt.client import Client, MQTTMessage

from ryobi_gdo_2_mqtt.logging import log


class RyobiDevice:
    """Represents a Ryobi garage door opener with MQTT entities."""

    def __init__(self, device_id: str, device_name: str, mqtt_settings: MQTTSettings.MQTT, websocket, api_client):
        """Initialize a Ryobi device with MQTT entities.

        Args:
            device_id: Ryobi device ID
            device_name: Human-readable device name
            mqtt_settings: MQTT connection settings
            websocket: WebSocket connection for sending commands
            api_client: API client for getting module information
        """
        self.device_id = device_id
        self.device_name = device_name
        self.websocket = websocket
        self.api_client = api_client

        # Create HA device info
        self.device_info = DeviceInfo(
            name=device_name,
            identifiers=device_id,
            manufacturer="Ryobi",
            model="Garage Door Opener",
        )

        # Create cover entity for garage door
        cover_info = CoverInfo(
            name=f"{device_name} Door",
            unique_id=f"{device_id}_door",
            device=self.device_info,
        )
        cover_settings = MQTTSettings(mqtt=mqtt_settings, entity=cover_info)
        self.cover = Cover(cover_settings, self._handle_door_command)

        # Create switch entity for light
        light_info = SwitchInfo(
            name=f"{device_name} Light",
            unique_id=f"{device_id}_light",
            device=self.device_info,
        )
        light_settings = MQTTSettings(mqtt=mqtt_settings, entity=light_info)
        self.light = Switch(light_settings, self._handle_light_command)

        # Create binary sensor for battery (if applicable)
        battery_info = BinarySensorInfo(
            name=f"{device_name} Battery",
            unique_id=f"{device_id}_battery",
            device_class="battery",
            device=self.device_info,
        )
        battery_settings = MQTTSettings(mqtt=mqtt_settings, entity=battery_info)
        self.battery_sensor = BinarySensor(battery_settings)

        # Initialize states
        self.cover.closed()  # Makes it discoverable
        self.light.off()

    def _handle_door_command(self, client: Client, user_data, message: MQTTMessage):
        """Handle door commands from Home Assistant."""
        payload = message.payload.decode()
        log.info("Received door command for %s: %s", self.device_id, payload)

        # Get module information dynamically
        port_id = self.api_client.get_module(self.device_id, "garageDoor")
        module_type = self.api_client.get_module_type("garageDoor")

        if port_id is None or module_type is None:
            log.error("Cannot send door command: module info not available")
            return

        if payload == "OPEN":
            self.cover.opening()
            # Send command via WebSocket: value=1 (open)
            asyncio.create_task(self.websocket.send_message(port_id, module_type, "doorCommand", 1))
        elif payload == "CLOSE":
            self.cover.closing()
            # Send command via WebSocket: value=0 (close)
            asyncio.create_task(self.websocket.send_message(port_id, module_type, "doorCommand", 0))
        elif payload == "STOP":
            # Send stop command: value=2 (stop)
            asyncio.create_task(self.websocket.send_message(port_id, module_type, "doorCommand", 2))
            self.cover.stopped()

    def _handle_light_command(self, client: Client, user_data, message: MQTTMessage):
        """Handle light commands from Home Assistant."""
        payload = message.payload.decode()
        log.info("Received light command for %s: %s", self.device_id, payload)

        # Get module information dynamically
        port_id = self.api_client.get_module(self.device_id, "garageLight")
        module_type = self.api_client.get_module_type("garageLight")

        if port_id is None or module_type is None:
            log.error("Cannot send light command: module info not available")
            return

        if payload == "ON":
            # Send light on command via WebSocket: value=1
            asyncio.create_task(self.websocket.send_message(port_id, module_type, "lightState", 1))
            self.light.on()
        elif payload == "OFF":
            # Send light off command via WebSocket: value=0
            asyncio.create_task(self.websocket.send_message(port_id, module_type, "lightState", 0))
            self.light.off()

    def update_door_state(self, state: str):
        """Update door state from WebSocket data.

        Args:
            state: Door state (e.g., "open", "closed", "opening", "closing")
        """
        log.debug("Updating door state for %s: %s", self.device_id, state)

        if state == "open":
            self.cover.open()
        elif state == "closed":
            self.cover.closed()
        elif state == "opening":
            self.cover.opening()
        elif state == "closing":
            self.cover.closing()
        elif state == "stopped":
            self.cover.stopped()

    def update_light_state(self, state: bool):
        """Update light state from WebSocket data.

        Args:
            state: Light state (True=on, False=off)
        """
        log.debug("Updating light state for %s: %s", self.device_id, state)

        if state:
            self.light.on()
        else:
            self.light.off()

    def update_battery_level(self, level: int):
        """Update battery level from WebSocket data.

        Args:
            level: Battery level percentage
        """
        log.debug("Updating battery level for %s: %s", self.device_id, level)

        # Consider battery low if below 20%
        if level < 20:
            self.battery_sensor.on()  # Battery low
        else:
            self.battery_sensor.off()  # Battery OK
