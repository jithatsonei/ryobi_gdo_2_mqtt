import asyncio
import logging
import ssl
import sys
from typing import Any

import aiohttp
import certifi
from aiohttp import TCPConnector
from ha_mqtt_discoverable import Settings as MQTTSettings

from ryobi_gdo_2_mqtt.api import RyobiApiClient
from ryobi_gdo_2_mqtt.device_manager import RyobiDevice
from ryobi_gdo_2_mqtt.logging import log
from ryobi_gdo_2_mqtt.settings import Settings
from ryobi_gdo_2_mqtt.websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_STOPPED,
    RyobiWebSocket,
)


class RyobiGDO2MQTT:
    """RyobiGDO 2 MQTT service."""

    def __init__(self):
        """Initialize the service."""
        self.websockets: dict[str, RyobiWebSocket] = {}
        self.devices: dict[str, RyobiDevice] = {}
        self.session: aiohttp.ClientSession | None = None
        self.api_client: RyobiApiClient | None = None
        self.mqtt_settings: MQTTSettings.MQTT | None = None

    def __call__(self, settings: Settings) -> None:
        """Start the RyobiGDO 2 MQTT service."""
        try:
            asyncio.run(self._run(settings))
        except KeyboardInterrupt:
            log.info("Received shutdown signal")
        except Exception as ex:
            log.critical("Unhandled exception occurred, exiting")
            log.exception(ex)
            sys.exit(1)

    async def _run(self, settings: Settings) -> None:
        """Run the main async logic."""
        # Set log level for all loggers
        log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
        log.setLevel(log_level)

        # Also set for ha-mqtt-discoverable and paho
        logging.getLogger("ha_mqtt_discoverable").setLevel(log_level)
        logging.getLogger("paho.mqtt.client").setLevel(log_level)

        log.info("Log level set to: %s", settings.log_level)

        # Create aiohttp session
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            self.session = session

            # Initialize API client
            self.api_client = RyobiApiClient(
                username=settings.email,
                password=settings.password.get_secret_value(),
                session=session,
            )

            # Authenticate and get API key
            log.info("Authenticating with Ryobi API...")
            if not await self.api_client.get_api_key():
                log.error("Failed to authenticate with Ryobi API")
                sys.exit(1)

            log.info("Successfully authenticated with Ryobi API")

            # Get all devices
            log.info("Fetching all devices...")
            all_devices = await self.api_client.get_devices()
            if not all_devices:
                log.error("No devices found in account")
                sys.exit(1)
            log.info("Found devices: %s", all_devices)

            # Initialize MQTT settings
            self.mqtt_settings = MQTTSettings.MQTT(
                host=settings.mqtt_host,
                port=settings.mqtt_port,
                username=settings.mqtt_user if settings.mqtt_user else None,
                password=settings.mqtt_password.get_secret_value() if settings.mqtt_password else None,
            )

            # Create WebSocket connections and MQTT entities for each device
            tasks = []
            for device_id, device_name in all_devices.items():
                log.info("Setting up device: %s (%s)", device_name, device_id)

                # Get initial device state and module information
                log.info("Fetching initial state for device: %s", device_id)
                device_data = await self.api_client.update_device(device_id)
                if not device_data:
                    log.error("Failed to get initial state for device: %s", device_id)
                    continue

                # Create WebSocket
                ws = RyobiWebSocket(
                    callback=self._create_websocket_callback(device_id),
                    username=settings.email,
                    apikey=self.api_client.api_key,
                    device=device_id,
                    session=session,
                )
                self.websockets[device_id] = ws

                # Create MQTT device entities
                device = RyobiDevice(
                    device_id=device_id,
                    device_name=device_name,
                    mqtt_settings=self.mqtt_settings,
                    websocket=ws,
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

                # Start WebSocket listening
                tasks.append(asyncio.create_task(ws.listen()))

            # Wait for all WebSocket tasks
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                log.info("Shutting down WebSocket connections...")
                for ws in self.websockets.values():
                    await ws.close()

    def _create_websocket_callback(self, device_id: str):
        """Create a callback function for a specific device's WebSocket.

        Args:
            device_id: The device ID this callback is for

        Returns:
            Async callback function
        """

        async def callback(signal: str, data: Any, error: Any = None) -> None:
            """Handle WebSocket callbacks for a specific device."""
            if signal == SIGNAL_CONNECTION_STATE:
                if data == STATE_CONNECTED:
                    log.info("WebSocket connected for device: %s", device_id)
                elif data == STATE_STOPPED:
                    log.warning("WebSocket stopped for device: %s. Reason: %s", device_id, error)
                else:
                    log.debug("WebSocket state for %s: %s", device_id, data)
            elif signal == "data":
                log.debug("Received data for device %s: %s", device_id, data)
                await self._handle_device_update(device_id, data)

        return callback

    async def _handle_device_update(self, device_id: str, data: dict) -> None:
        """Process device updates from WebSocket.

        Args:
            device_id: The device ID
            data: The device update data
        """
        device = self.devices.get(device_id)
        if not device:
            log.warning("Received data for unknown device: %s", device_id)
            return

        # Parse the WebSocket message
        # Expected format from Ryobi:
        # {
        #   "method": "wskAttributeUpdateNtfy",
        #   "params": {
        #     "topic": "device_id.wskAttributeUpdateNtfy",
        #     "attribute": "doorState",
        #     "value": 0  # or other value
        #   }
        # }

        try:
            if data.get("method") == "wskAttributeUpdateNtfy":
                params = data.get("params", {})

                # Parse the topic to get the attribute path
                # Format: "device_id.wskAttributeUpdateNtfy"
                # The actual attribute info is in the params
                for key in params:
                    if key in ["topic", "varName", "id"]:
                        continue

                    log.debug("Websocket parsing update for item %s: %s", key, params[key])

                    # Extract module name from key (e.g., "garageDoor_1.doorState")
                    if "." in key:
                        module_name = key.split(".")[1]
                    else:
                        module_name = key

                    value = params[key].get("value") if isinstance(params[key], dict) else params[key]

                    # Garage Door updates
                    if "garageDoor" in key:
                        if module_name == "doorState":
                            door_state = self.api_client.DOOR_STATE.get(str(value), "unknown")
                            if door_state != "unknown":
                                device.update_door_state(door_state)
                        elif module_name == "motionSensor":
                            # Could add motion sensor entity
                            log.debug("Motion sensor: %s", value)
                        elif module_name == "vacationMode":
                            log.debug("Vacation mode: %s", value)
                        elif module_name == "sensorFlag":
                            log.debug("Safety sensor: %s", value)

                    # Garage Light updates
                    elif "garageLight" in key:
                        if module_name == "lightState":
                            device.update_light_state(bool(value))

                    # Battery updates
                    elif "backupCharger" in key:
                        if module_name == "chargeLevel":
                            device.update_battery_level(int(value))

                    # Other modules
                    elif "parkAssistLaser" in key:
                        log.debug("Park assist: %s", value)
                    elif "btSpeaker" in key:
                        log.debug("Bluetooth speaker: %s", value)
                    elif "inflator" in key:
                        log.debug("Inflator: %s", value)
                    elif "fan" in key:
                        log.debug("Fan: %s", value)
                    else:
                        log.debug("Unhandled module update: %s = %s", key, value)

        except Exception as ex:
            log.error("Error processing device update for %s: %s", device_id, ex)
            log.exception(ex)


ryobi_gdo2_mqtt = RyobiGDO2MQTT()
