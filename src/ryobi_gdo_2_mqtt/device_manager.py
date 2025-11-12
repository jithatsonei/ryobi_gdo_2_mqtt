import asyncio

from ha_mqtt_discoverable import DeviceInfo, Settings as MQTTSettings
from ha_mqtt_discoverable.sensors import BinarySensor, BinarySensorInfo, Cover, CoverInfo, Switch, SwitchInfo
from paho.mqtt.client import Client, MQTTMessage

from ryobi_gdo_2_mqtt.constants import (
    BATTERY_LOW_THRESHOLD,
    DoorCommandPayloads,
    DoorCommands,
    LightCommandPayloads,
    LightStates,
)
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
        self._pending_tasks: set[asyncio.Task] = set()

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

        if payload == DoorCommandPayloads.OPEN:
            self.cover.opening()
            task = asyncio.create_task(
                self.websocket.send_message(port_id, module_type, "doorCommand", DoorCommands.OPEN)
            )
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)
        elif payload == DoorCommandPayloads.CLOSE:
            self.cover.closing()
            task = asyncio.create_task(
                self.websocket.send_message(port_id, module_type, "doorCommand", DoorCommands.CLOSE)
            )
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)
        elif payload == DoorCommandPayloads.STOP:
            task = asyncio.create_task(
                self.websocket.send_message(port_id, module_type, "doorCommand", DoorCommands.STOP)
            )
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)
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

        if payload == LightCommandPayloads.ON:
            task = asyncio.create_task(self.websocket.send_message(port_id, module_type, "lightState", LightStates.ON))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)
            self.light.on()
        elif payload == LightCommandPayloads.OFF:
            task = asyncio.create_task(self.websocket.send_message(port_id, module_type, "lightState", LightStates.OFF))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)
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

        if level < BATTERY_LOW_THRESHOLD:
            self.battery_sensor.on()  # Battery low
        else:
            self.battery_sensor.off()  # Battery OK

    async def cleanup(self):
        """Clean up device resources."""
        log.debug("Cleaning up device: %s", self.device_id)
        # Cancel all pending tasks
        for task in self._pending_tasks:
            if not task.done():
                task.cancel()
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
        self._pending_tasks.clear()


class DeviceManager:
    """Manages multiple Ryobi devices and their MQTT entities."""

    def __init__(self, mqtt_settings: MQTTSettings.MQTT, api_client):
        """Initialize the device manager.

        Args:
            mqtt_settings: MQTT connection settings
            api_client: API client for getting module information
        """
        self.devices: dict[str, RyobiDevice] = {}
        self.mqtt_settings = mqtt_settings
        self.api_client = api_client
        self.parser = None

    async def setup_device(self, device_id: str, device_name: str, websocket) -> RyobiDevice:
        """Set up a single device with initial state.

        Args:
            device_id: Ryobi device ID
            device_name: Human-readable device name
            websocket: WebSocket connection for the device

        Returns:
            Configured RyobiDevice instance
        """
        log.info("Setting up device: %s (%s)", device_name, device_id)

        # Get initial device state and module information
        log.info("Fetching initial state for device: %s", device_id)
        device_data = await self.api_client.update_device(device_id)
        if not device_data:
            raise ValueError(f"Failed to get initial state for device: {device_id}")

        # Create MQTT device entities
        device = RyobiDevice(
            device_id=device_id,
            device_name=device_name,
            mqtt_settings=self.mqtt_settings,
            websocket=websocket,
            api_client=self.api_client,
        )
        self.devices[device_id] = device

        # Set initial states from device data
        if device_data.door_state is not None:
            device.update_door_state(device_data.door_state)
        if device_data.light_state is not None:
            device.update_light_state(bool(device_data.light_state))
        if device_data.battery_level is not None:
            device.update_battery_level(device_data.battery_level)

        return device

    async def handle_device_update(self, device_id: str, data: dict) -> None:
        """Process device updates from WebSocket.

        Args:
            device_id: The device ID
            data: The device update data
        """
        device = self.devices.get(device_id)
        if not device:
            log.warning("Received data for unknown device: %s", device_id)
            return

        # Parse the WebSocket message using the parser
        updates = self.parser.parse_attribute_update(data)

        # Apply updates to the device
        if "door_state" in updates:
            device.update_door_state(updates["door_state"])

        if "light_state" in updates:
            device.update_light_state(updates["light_state"])

        if "battery_level" in updates:
            device.update_battery_level(updates["battery_level"])
