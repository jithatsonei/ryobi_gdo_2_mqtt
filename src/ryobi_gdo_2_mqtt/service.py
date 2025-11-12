"""Service coordinator for managing API client, WebSocket connections, and device manager."""

from typing import Any

from aiohttp import ClientSession

from ryobi_gdo_2_mqtt.api import RyobiApiClient
from ryobi_gdo_2_mqtt.constants import WebSocketState
from ryobi_gdo_2_mqtt.device_manager import DeviceManager
from ryobi_gdo_2_mqtt.logging import log
from ryobi_gdo_2_mqtt.websocket import SIGNAL_CONNECTION_STATE, RyobiWebSocket


class ServiceCoordinator:
    """Coordinates API client, WebSocket connections, and device manager."""

    def __init__(self, api_client: RyobiApiClient, device_manager: DeviceManager):
        """Initialize the service coordinator.

        Args:
            api_client: The Ryobi API client
            device_manager: The device manager
        """
        self.api_client = api_client
        self.device_manager = device_manager
        self.websockets: dict[str, RyobiWebSocket] = {}

    def create_websocket_callback(self, device_id: str):
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

    async def setup_device(
        self, device_id: str, device_name: str, username: str, apikey: str, session: ClientSession
    ) -> RyobiWebSocket:
        """Setup a device with WebSocket and MQTT entities.

        Args:
            device_id: The device ID
            device_name: The device name
            username: Ryobi username
            apikey: Ryobi API key
            session: aiohttp ClientSession

        Returns:
            The created WebSocket instance
        """
        # Create WebSocket
        ws = RyobiWebSocket(
            callback=self.create_websocket_callback(device_id),
            username=username,
            apikey=apikey,
            device=device_id,
            session=session,
        )
        self.websockets[device_id] = ws

        # Setup device through device manager
        await self.device_manager.setup_device(device_id, device_name, ws)

        return ws

    async def cleanup(self):
        """Clean up coordinator resources."""
        log.info("Cleaning up service coordinator...")

        # Clean up devices
        for device in self.device_manager.devices.values():
            await device.cleanup()

        # Close WebSockets
        for ws in self.websockets.values():
            await ws.close()
