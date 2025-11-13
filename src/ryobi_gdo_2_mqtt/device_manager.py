import asyncio
from concurrent.futures import Future
from dataclasses import dataclass

from ha_mqtt_discoverable import DeviceInfo, Settings as MQTTSettings
from ha_mqtt_discoverable.sensors import (
    BinarySensor,
    BinarySensorInfo,
    Cover,
    CoverInfo,
    Number,
    NumberInfo,
    Sensor,
    SensorInfo,
    Switch,
    SwitchInfo,
)
from paho.mqtt.client import Client, MQTTMessage

from ryobi_gdo_2_mqtt.constants import (
    BATTERY_LOW_THRESHOLD,
    DoorCommandPayloads,
    DoorCommands,
    LightCommandPayloads,
    LightStates,
)
from ryobi_gdo_2_mqtt.logging import log


@dataclass
class ModuleConfig:
    """Configuration for a device module."""

    name: str
    module_type: int
    attribute_name: str


# Module configurations
MODULES = {
    "garageDoor": ModuleConfig(
        name="garageDoor",
        module_type=5,
        attribute_name="doorCommand",
    ),
    "garageLight": ModuleConfig(
        name="garageLight",
        module_type=5,
        attribute_name="lightState",
    ),
    "backupCharger": ModuleConfig(
        name="backupCharger",
        module_type=6,
        attribute_name="chargeLevel",
    ),
    "wifiModule": ModuleConfig(
        name="wifiModule",
        module_type=7,
        attribute_name="rssi",
    ),
    "parkAssistLaser": ModuleConfig(
        name="parkAssistLaser",
        module_type=1,
        attribute_name="moduleState",
    ),
    "inflator": ModuleConfig(
        name="inflator",
        module_type=4,
        attribute_name="moduleState",
    ),
    "btSpeaker": ModuleConfig(
        name="btSpeaker",
        module_type=2,
        attribute_name="moduleState",
    ),
    "fan": ModuleConfig(
        name="fan",
        module_type=3,
        attribute_name="speed",
    ),
}


class EntityFactory:
    """Factory for creating MQTT entities."""

    @staticmethod
    def create_cover(
        device_id: str, device_name: str, device_info: DeviceInfo, mqtt_settings: MQTTSettings.MQTT, callback
    ) -> Cover:
        """Create a cover entity for garage door."""
        info = CoverInfo(
            name=f"{device_name} Door",
            unique_id=f"{device_id}_door",
            device=device_info,
        )
        settings = MQTTSettings(mqtt=mqtt_settings, entity=info)
        return Cover(settings, callback)

    @staticmethod
    def create_switch(
        device_id: str,
        device_name: str,
        device_info: DeviceInfo,
        mqtt_settings: MQTTSettings.MQTT,
        callback,
        entity_type: str,
    ) -> Switch:
        """Create a switch entity."""
        names = {
            "light": "Light",
            "vacation": "Vacation Mode",
            "park_assist": "Park Assist",
            "inflator": "Inflator",
            "bt_speaker": "Bluetooth Speaker",
        }
        info = SwitchInfo(
            name=f"{device_name} {names[entity_type]}",
            unique_id=f"{device_id}_{entity_type}",
            device=device_info,
        )
        settings = MQTTSettings(mqtt=mqtt_settings, entity=info)
        return Switch(settings, callback)

    @staticmethod
    def create_binary_sensor(
        device_id: str, device_name: str, device_info: DeviceInfo, mqtt_settings: MQTTSettings.MQTT, sensor_type: str
    ) -> BinarySensor:
        """Create a binary sensor entity."""
        names = {
            "battery": "Battery",
            "motion": "Motion",
        }
        device_classes = {
            "battery": "battery",
            "motion": "motion",
        }
        info = BinarySensorInfo(
            name=f"{device_name} {names[sensor_type]}",
            unique_id=f"{device_id}_{sensor_type}",
            device_class=device_classes[sensor_type],
            device=device_info,
        )
        settings = MQTTSettings(mqtt=mqtt_settings, entity=info)
        return BinarySensor(settings)

    @staticmethod
    def create_sensor(
        device_id: str,
        device_name: str,
        device_info: DeviceInfo,
        mqtt_settings: MQTTSettings.MQTT,
        sensor_type: str,
        device_class: str | None = None,
        unit: str | None = None,
    ) -> Sensor:
        """Create a sensor entity."""
        names = {
            "wifi": "WiFi Signal",
        }
        info = SensorInfo(
            name=f"{device_name} {names[sensor_type]}",
            unique_id=f"{device_id}_{sensor_type}",
            device_class=device_class,
            unit_of_measurement=unit,
            device=device_info,
        )
        settings = MQTTSettings(mqtt=mqtt_settings, entity=info)
        return Sensor(settings)

    @staticmethod
    def create_number(
        device_id: str,
        device_name: str,
        device_info: DeviceInfo,
        mqtt_settings: MQTTSettings.MQTT,
        callback,
        entity_type: str,
        min_value: int = 0,
        max_value: int = 100,
        step: int = 1,
    ) -> Number:
        """Create a number entity."""
        names = {
            "fan": "Fan Speed",
        }
        info = NumberInfo(
            name=f"{device_name} {names[entity_type]}",
            unique_id=f"{device_id}_{entity_type}",
            min=min_value,
            max=max_value,
            step=step,
            device=device_info,
        )
        settings = MQTTSettings(mqtt=mqtt_settings, entity=info)
        return Number(settings, callback)


class CommandHandler:
    """Base class for handling device commands."""

    def __init__(self, device):
        """Initialize command handler.

        Args:
            device: RyobiDevice instance
        """
        self.device = device

    def send_command(self, module_name: str, value: int, attribute: str | None = None):
        """Send a command to the device.

        Args:
            module_name: Name of the module (e.g., "garageDoor", "garageLight")
            value: Value to set
            attribute: Attribute to set (optional, uses module config default if not provided)
        """
        if module_name not in MODULES:
            log.error("Unknown module: %s", module_name)
            return

        module_config = MODULES[module_name]
        port_id = self.device.api_client.get_module(self.device.device_id, module_name)

        if port_id is None:
            log.error("Cannot send %s command: module info not available", module_name)
            return

        # Use provided attribute or default from config
        attr = attribute if attribute is not None else module_config.attribute_name

        future = asyncio.run_coroutine_threadsafe(
            self.device.websocket.send_message(port_id, module_config.module_type, attr, value), self.device.loop
        )
        self.device._pending_futures.add(future)
        future.add_done_callback(self.device._pending_futures.discard)


class RyobiDevice:
    """Represents a Ryobi garage door opener with MQTT entities."""

    def __init__(
        self,
        device_id: str,
        device_name: str,
        mqtt_settings: MQTTSettings.MQTT,
        websocket,
        api_client,
        loop: asyncio.AbstractEventLoop,
    ):
        """Initialize a Ryobi device with MQTT entities.

        Args:
            device_id: Ryobi device ID
            device_name: Human-readable device name
            mqtt_settings: MQTT connection settings
            websocket: WebSocket connection for sending commands
            api_client: API client for getting module information
            loop: Event loop for scheduling coroutines
        """
        self.device_id = device_id
        self.device_name = device_name
        self.websocket = websocket
        self.api_client = api_client
        self.loop = loop
        self._pending_tasks: set[asyncio.Task] = set()
        self._pending_futures: set[Future] = set()

        # Create HA device info
        self.device_info = DeviceInfo(
            name=device_name,
            identifiers=device_id,
            manufacturer="Ryobi",
            model="Garage Door Opener",
        )

        # Create command handler
        self.command_handler = CommandHandler(self)

        # Create entities using factory
        self.cover = EntityFactory.create_cover(
            device_id, device_name, self.device_info, mqtt_settings, self._handle_door_command
        )
        self.light = EntityFactory.create_switch(
            device_id, device_name, self.device_info, mqtt_settings, self._handle_light_command, "light"
        )
        self.battery_sensor = EntityFactory.create_binary_sensor(
            device_id, device_name, self.device_info, mqtt_settings, "battery"
        )
        self.motion_sensor = EntityFactory.create_binary_sensor(
            device_id, device_name, self.device_info, mqtt_settings, "motion"
        )
        self.wifi_sensor = EntityFactory.create_sensor(
            device_id, device_name, self.device_info, mqtt_settings, "wifi", "signal_strength", "dBm"
        )
        self.vacation_switch = EntityFactory.create_switch(
            device_id, device_name, self.device_info, mqtt_settings, self._handle_vacation_command, "vacation"
        )
        self.park_assist_switch = EntityFactory.create_switch(
            device_id, device_name, self.device_info, mqtt_settings, self._handle_park_assist_command, "park_assist"
        )
        self.inflator_switch = EntityFactory.create_switch(
            device_id, device_name, self.device_info, mqtt_settings, self._handle_inflator_command, "inflator"
        )
        self.bt_speaker_switch = EntityFactory.create_switch(
            device_id, device_name, self.device_info, mqtt_settings, self._handle_bt_speaker_command, "bt_speaker"
        )
        self.fan_number = EntityFactory.create_number(
            device_id, device_name, self.device_info, mqtt_settings, self._handle_fan_command, "fan"
        )

        # Initialize states
        self.cover.closed()  # Makes it discoverable
        self.light.off()
        self.vacation_switch.off()

    def _handle_door_command(self, client: Client, user_data, message: MQTTMessage):
        """Handle door commands from Home Assistant."""
        payload = message.payload.decode()
        log.info("Received door command for %s: %s", self.device_id, payload)

        if payload == DoorCommandPayloads.OPEN:
            self.cover.opening()
            self.command_handler.send_command("garageDoor", DoorCommands.OPEN)
        elif payload == DoorCommandPayloads.CLOSE:
            self.cover.closing()
            self.command_handler.send_command("garageDoor", DoorCommands.CLOSE)
        elif payload == DoorCommandPayloads.STOP:
            self.command_handler.send_command("garageDoor", DoorCommands.STOP)
            self.cover.stopped()

    def _handle_light_command(self, client: Client, user_data, message: MQTTMessage):
        """Handle light commands from Home Assistant."""
        payload = message.payload.decode()
        log.info("Received light command for %s: %s", self.device_id, payload)

        if payload == LightCommandPayloads.ON:
            self.command_handler.send_command("garageLight", LightStates.ON)
            self.light.on()
        elif payload == LightCommandPayloads.OFF:
            self.command_handler.send_command("garageLight", LightStates.OFF)
            self.light.off()

    def _handle_vacation_command(self, client: Client, user_data, message: MQTTMessage):
        """Handle vacation mode commands from Home Assistant."""
        payload = message.payload.decode()
        log.info("Received vacation mode command for %s: %s", self.device_id, payload)

        value = 1 if payload == "ON" else 0
        self.command_handler.send_command("garageDoor", value, "vacationMode")

        if value:
            self.vacation_switch.on()
        else:
            self.vacation_switch.off()

    def _handle_park_assist_command(self, client: Client, user_data, message: MQTTMessage):
        """Handle park assist commands from Home Assistant."""
        payload = message.payload.decode()
        log.info("Received park assist command for %s: %s", self.device_id, payload)

        value = 1 if payload == "ON" else 0
        self.command_handler.send_command("parkAssistLaser", value)

        if value:
            self.park_assist_switch.on()
        else:
            self.park_assist_switch.off()

    def _handle_inflator_command(self, client: Client, user_data, message: MQTTMessage):
        """Handle inflator commands from Home Assistant."""
        payload = message.payload.decode()
        log.info("Received inflator command for %s: %s", self.device_id, payload)

        value = 1 if payload == "ON" else 0
        self.command_handler.send_command("inflator", value)

        if value:
            self.inflator_switch.on()
        else:
            self.inflator_switch.off()

    def _handle_bt_speaker_command(self, client: Client, user_data, message: MQTTMessage):
        """Handle bluetooth speaker commands from Home Assistant."""
        payload = message.payload.decode()
        log.info("Received bluetooth speaker command for %s: %s", self.device_id, payload)

        value = 1 if payload == "ON" else 0
        self.command_handler.send_command("btSpeaker", value)

        if value:
            self.bt_speaker_switch.on()
        else:
            self.bt_speaker_switch.off()

    def _handle_fan_command(self, client: Client, user_data, message: MQTTMessage):
        """Handle fan speed commands from Home Assistant."""
        speed = int(message.payload.decode())
        log.info("Received fan speed command for %s: %s", self.device_id, speed)

        self.command_handler.send_command("fan", speed)
        self.fan_number.set_value(speed)

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

    def update_motion_state(self, state: int):
        """Update motion sensor state from WebSocket data.

        Args:
            state: Motion state (1=motion detected, 0=no motion)
        """
        log.debug("Updating motion state for %s: %s", self.device_id, state)

        if state:
            self.motion_sensor.on()
        else:
            self.motion_sensor.off()

    def update_wifi_rssi(self, rssi: int):
        """Update WiFi signal strength from WebSocket data.

        Args:
            rssi: WiFi signal strength in dBm
        """
        log.debug("Updating WiFi RSSI for %s: %s", self.device_id, rssi)
        self.wifi_sensor.set_state(rssi)

    def update_vacation_mode(self, state: int):
        """Update vacation mode state from WebSocket data.

        Args:
            state: Vacation mode state (1=enabled, 0=disabled)
        """
        log.debug("Updating vacation mode for %s: %s", self.device_id, state)

        if state:
            self.vacation_switch.on()
        else:
            self.vacation_switch.off()

    def update_park_assist(self, state: int):
        """Update park assist state from WebSocket data.

        Args:
            state: Park assist state (1=enabled, 0=disabled)
        """
        log.debug("Updating park assist for %s: %s", self.device_id, state)

        if state:
            self.park_assist_switch.on()
        else:
            self.park_assist_switch.off()

    def update_inflator(self, state: int):
        """Update inflator state from WebSocket data.

        Args:
            state: Inflator state (1=enabled, 0=disabled)
        """
        log.debug("Updating inflator for %s: %s", self.device_id, state)

        if state:
            self.inflator_switch.on()
        else:
            self.inflator_switch.off()

    def update_bt_speaker(self, state: int):
        """Update bluetooth speaker state from WebSocket data.

        Args:
            state: Bluetooth speaker state (1=enabled, 0=disabled)
        """
        log.debug("Updating bluetooth speaker for %s: %s", self.device_id, state)

        if state:
            self.bt_speaker_switch.on()
        else:
            self.bt_speaker_switch.off()

    def update_fan_speed(self, speed: int):
        """Update fan speed from WebSocket data.

        Args:
            speed: Fan speed (0-100)
        """
        log.debug("Updating fan speed for %s: %s", self.device_id, speed)
        self.fan_number.set_value(speed)

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

        # Cancel all pending futures
        for future in self._pending_futures:
            if not future.done():
                future.cancel()
        self._pending_futures.clear()


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

        # Get current event loop
        loop = asyncio.get_running_loop()

        # Create MQTT device entities
        device = RyobiDevice(
            device_id=device_id,
            device_name=device_name,
            mqtt_settings=self.mqtt_settings,
            websocket=websocket,
            api_client=self.api_client,
            loop=loop,
        )
        self.devices[device_id] = device

        # Set initial states from device data
        if device_data.door_state is not None:
            device.update_door_state(device_data.door_state)
        if device_data.light_state is not None:
            device.update_light_state(bool(device_data.light_state))
        if device_data.battery_level is not None:
            device.update_battery_level(device_data.battery_level)
        if device_data.motion is not None:
            device.update_motion_state(device_data.motion)
        if device_data.wifi_rssi is not None:
            device.update_wifi_rssi(device_data.wifi_rssi)
        if device_data.vacation_mode is not None:
            device.update_vacation_mode(device_data.vacation_mode)
        if device_data.park_assist is not None:
            device.update_park_assist(device_data.park_assist)
        if device_data.inflator is not None:
            device.update_inflator(device_data.inflator)
        if device_data.bt_speaker is not None:
            device.update_bt_speaker(device_data.bt_speaker)
        if device_data.fan is not None:
            device.update_fan_speed(device_data.fan)

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

        if "motion" in updates:
            device.update_motion_state(updates["motion"])

        if "wifi_rssi" in updates:
            device.update_wifi_rssi(updates["wifi_rssi"])

        if "vacation_mode" in updates:
            device.update_vacation_mode(updates["vacation_mode"])

        if "park_assist" in updates:
            device.update_park_assist(updates["park_assist"])

        if "inflator" in updates:
            device.update_inflator(updates["inflator"])

        if "bt_speaker" in updates:
            device.update_bt_speaker(updates["bt_speaker"])

        if "fan" in updates:
            device.update_fan_speed(updates["fan"])
