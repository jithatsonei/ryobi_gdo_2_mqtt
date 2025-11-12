"""Tests for service coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ryobi_gdo_2_mqtt.constants import WebSocketState
from ryobi_gdo_2_mqtt.service import ServiceCoordinator
from ryobi_gdo_2_mqtt.websocket import SIGNAL_CONNECTION_STATE


@pytest.fixture
def mock_api_client():
    """Create mock API client."""
    return MagicMock()


@pytest.fixture
def mock_device_manager():
    """Create mock device manager."""
    manager = MagicMock()
    manager.devices = {}
    manager.handle_device_update = AsyncMock()
    manager.setup_device = AsyncMock()
    return manager


@pytest.fixture
def mock_session():
    """Create mock aiohttp session."""
    return MagicMock()


@pytest.fixture
def coordinator(mock_api_client, mock_device_manager):
    """Create a service coordinator instance."""
    return ServiceCoordinator(api_client=mock_api_client, device_manager=mock_device_manager)


class TestServiceCoordinator:
    """Tests for ServiceCoordinator."""

    def test_initialization(self, coordinator, mock_api_client, mock_device_manager):
        """Test coordinator initialization."""
        assert coordinator.api_client is mock_api_client
        assert coordinator.device_manager is mock_device_manager
        assert coordinator.websockets == {}

    @pytest.mark.asyncio
    async def test_setup_device(self, coordinator, mock_session):
        """Test setting up a device."""
        device_id = "test_device"
        device_name = "Test Device"
        username = "test@example.com"
        apikey = "test_api_key"

        ws = await coordinator.setup_device(device_id, device_name, username, apikey, mock_session)

        assert ws is not None
        assert device_id in coordinator.websockets
        assert coordinator.websockets[device_id] is ws
        coordinator.device_manager.setup_device.assert_called_once_with(device_id, device_name, ws)

    @pytest.mark.asyncio
    async def test_websocket_callback_handles_connected_state(self, coordinator):
        """Test WebSocket callback handles CONNECTED state."""
        device_id = "test_device"
        callback = coordinator.create_websocket_callback(device_id)

        # Should not raise
        await callback(SIGNAL_CONNECTION_STATE, WebSocketState.CONNECTED)

    @pytest.mark.asyncio
    async def test_websocket_callback_handles_stopped_state(self, coordinator):
        """Test WebSocket callback handles STOPPED state."""
        device_id = "test_device"
        callback = coordinator.create_websocket_callback(device_id)

        # Should not raise
        await callback(SIGNAL_CONNECTION_STATE, WebSocketState.STOPPED, error="Test error")

    @pytest.mark.asyncio
    async def test_websocket_callback_handles_data(self, coordinator):
        """Test WebSocket callback handles data signal."""
        device_id = "test_device"
        callback = coordinator.create_websocket_callback(device_id)
        test_data = {"test": "data"}

        await callback("data", test_data)

        coordinator.device_manager.handle_device_update.assert_called_once_with(device_id, test_data)

    @pytest.mark.asyncio
    async def test_cleanup_closes_websockets(self, coordinator, mock_session):
        """Test cleanup closes all WebSockets."""
        # Setup multiple devices
        device1_id = "device1"
        device2_id = "device2"

        ws1 = await coordinator.setup_device(device1_id, "Device 1", "user", "key", mock_session)
        ws2 = await coordinator.setup_device(device2_id, "Device 2", "user", "key", mock_session)

        ws1.close = AsyncMock()
        ws2.close = AsyncMock()

        await coordinator.cleanup()

        ws1.close.assert_called_once()
        ws2.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_cleans_up_devices(self, coordinator, mock_session):
        """Test cleanup calls cleanup on all devices."""
        # Setup a device
        device_id = "test_device"
        await coordinator.setup_device(device_id, "Test Device", "user", "key", mock_session)

        # Add mock devices to device manager
        mock_device1 = MagicMock()
        mock_device1.cleanup = AsyncMock()
        mock_device2 = MagicMock()
        mock_device2.cleanup = AsyncMock()

        coordinator.device_manager.devices = {"device1": mock_device1, "device2": mock_device2}

        await coordinator.cleanup()

        mock_device1.cleanup.assert_called_once()
        mock_device2.cleanup.assert_called_once()
