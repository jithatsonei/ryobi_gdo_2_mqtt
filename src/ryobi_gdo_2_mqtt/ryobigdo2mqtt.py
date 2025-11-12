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
from ryobi_gdo_2_mqtt.constants import WebSocketState
from ryobi_gdo_2_mqtt.device_manager import DeviceManager
from ryobi_gdo_2_mqtt.exceptions import RyobiApiError
from ryobi_gdo_2_mqtt.logging import log
from ryobi_gdo_2_mqtt.settings import Settings
from ryobi_gdo_2_mqtt.websocket import (
    SIGNAL_CONNECTION_STATE,
    RyobiWebSocket,
)
from ryobi_gdo_2_mqtt.websocket_parser import WebSocketMessageParser


class RyobiGDO2MQTT:
    """RyobiGDO 2 MQTT service."""

    def __init__(self):
        """Initialize the service."""
        self.websockets: dict[str, RyobiWebSocket] = {}
        self.session: aiohttp.ClientSession | None = None
        self.api_client: RyobiApiClient | None = None
        self.mqtt_settings: MQTTSettings.MQTT | None = None
        self.parser: WebSocketMessageParser | None = None
        self.device_manager: DeviceManager | None = None
        self._tasks: set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

    async def __aenter__(self):
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager and cleanup resources."""
        await self.cleanup()

    async def cleanup(self):
        """Clean up resources."""
        log.info("Cleaning up resources...")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Clean up devices
        if self.device_manager:
            for device in self.device_manager.devices.values():
                await device.cleanup()

        # Close WebSockets
        for ws in self.websockets.values():
            await ws.close()

        # Close session
        if self.session and not self.session.closed:
            await self.session.close()

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

            # Initialize WebSocket message parser
            self.parser = WebSocketMessageParser()

            # Initialize device manager
            self.device_manager = DeviceManager(
                mqtt_settings=None,  # Will be set after MQTT settings are initialized
                api_client=self.api_client,
            )

            # Authenticate and get API key
            log.info("Authenticating with Ryobi API...")
            try:
                await self.api_client.get_api_key()
                log.info("Successfully authenticated with Ryobi API")
            except RyobiApiError as e:
                log.error("Failed to authenticate with Ryobi API: %s", e)
                sys.exit(1)

            # Get all devices
            log.info("Fetching all devices...")
            try:
                all_devices = await self.api_client.get_devices()
                log.info("Found devices: %s", all_devices)
            except RyobiApiError as e:
                log.error("Failed to get devices: %s", e)
                sys.exit(1)

            # Initialize MQTT settings
            self.mqtt_settings = MQTTSettings.MQTT(
                host=settings.mqtt_host,
                port=settings.mqtt_port,
                username=settings.mqtt_user if settings.mqtt_user else None,
                password=settings.mqtt_password.get_secret_value() if settings.mqtt_password else None,
            )

            # Set MQTT settings and parser in device manager
            self.device_manager.mqtt_settings = self.mqtt_settings
            self.device_manager.parser = self.parser

            # Create WebSocket connections and MQTT entities for each device
            for device_id, device_name in all_devices.items():
                # Create WebSocket
                ws = RyobiWebSocket(
                    callback=self._create_websocket_callback(device_id),
                    username=settings.email,
                    apikey=self.api_client.api_key,
                    device=device_id,
                    session=session,
                )
                self.websockets[device_id] = ws

                # Setup device through device manager
                try:
                    await self.device_manager.setup_device(device_id, device_name, ws)
                except (ValueError, RyobiApiError) as e:
                    log.error("Failed to setup device %s: %s", device_id, e)
                    continue

                # Start WebSocket listening
                task = asyncio.create_task(ws.listen())
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

            # Wait for all WebSocket tasks
            try:
                await asyncio.gather(*self._tasks)
            except asyncio.CancelledError:
                log.info("Shutting down WebSocket connections...")
                await self.cleanup()

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
                if data == WebSocketState.CONNECTED:
                    log.info("WebSocket connected for device: %s", device_id)
                elif data == WebSocketState.STOPPED:
                    log.warning("WebSocket stopped for device: %s. Reason: %s", device_id, error)
                else:
                    log.debug("WebSocket state for %s: %s", device_id, data)
            elif signal == "data":
                log.debug("Received data for device %s: %s", device_id, data)
                await self.device_manager.handle_device_update(device_id, data)

        return callback


ryobi_gdo2_mqtt = RyobiGDO2MQTT()
