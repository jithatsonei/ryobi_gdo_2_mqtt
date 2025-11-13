"""Integration tests for Ryobi GDO 2 MQTT."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientSession

from ryobi_gdo_2_mqtt.api import RyobiApiClient
from ryobi_gdo_2_mqtt.device_manager import DeviceManager
from ryobi_gdo_2_mqtt.websocket_parser import WebSocketMessageParser
from tests.conftest import load_fixture


@pytest.fixture
def mock_mqtt_settings():
    """Create mock MQTT settings."""
    from ha_mqtt_discoverable import Settings as MQTTSettings

    return MQTTSettings.MQTT(host="localhost", port=1883)


class TestAuthenticationAndDiscovery:
    """Integration tests for authentication and device discovery flow."""

    @pytest.mark.asyncio
    async def test_full_authentication_and_discovery_flow(self, fixtures_dir):
        """Test complete flow: login → get API key → discover devices → fetch device state."""
        # Mock the HTTP session
        mock_session = MagicMock(spec=ClientSession)

        # Create API client
        api_client = RyobiApiClient(username="test@example.com", password="testpass", session=mock_session)

        # Mock the _process_request method to return fixture data
        login_response = load_fixture(fixtures_dir, "login_response.json")
        devices_response = load_fixture(fixtures_dir, "get_devices_response.json")
        device_update_response = load_fixture(fixtures_dir, "device_update_c4be84986d2e.json")

        async def mock_process_request(url, method, data):
            if "login" in url:
                return login_response
            elif "devices" in url and method == "get":
                if "c4be84986d2e" in url:
                    return device_update_response
                return devices_response
            return None

        api_client._process_request = AsyncMock(side_effect=mock_process_request)

        # Step 1: Authenticate and get API key
        auth_result = await api_client.get_api_key()
        assert auth_result is True
        assert api_client.api_key == "1234567890"

        # Step 2: Discover devices
        devices = await api_client.get_devices()
        assert len(devices) == 2
        assert "c4be84986d2e" in devices
        assert devices["c4be84986d2e"] == "Acura"

        # Step 3: Fetch device state
        device_data = await api_client.update_device("c4be84986d2e")
        assert device_data is not None
        assert device_data.door_state == "closed"
        assert device_data.light_state is False
        assert device_data.device_name == "Acura"

        # Step 4: Verify modules were indexed
        port_id = api_client.get_module("c4be84986d2e", "garageDoor")
        assert port_id == 7
        module_type = api_client.get_module_type("garageDoor")
        assert module_type == 5


class TestWebSocketIntegration:
    """Integration tests for WebSocket connection and message handling."""

    @pytest.mark.asyncio
    async def test_websocket_message_parsing_flow(self, fixtures_dir):
        """Test WebSocket message → parser → device update flow."""
        # Create parser
        parser = WebSocketMessageParser()

        # Test various WebSocket messages
        light_on_msg = load_fixture(fixtures_dir, "ws_message_1762952732.json")
        light_off_msg = load_fixture(fixtures_dir, "ws_message_1762952736.json")
        door_open_msg = load_fixture(fixtures_dir, "ws_message_1762952771.json")
        door_closed_msg = load_fixture(fixtures_dir, "ws_message_1762952798.json")

        # Parse light ON
        updates = parser.parse_attribute_update(light_on_msg)
        assert updates["light_state"] is True

        # Parse light OFF
        updates = parser.parse_attribute_update(light_off_msg)
        assert updates["light_state"] is False

        # Parse door OPEN
        updates = parser.parse_attribute_update(door_open_msg)
        assert updates["door_state"] == "open"

        # Parse door CLOSED
        updates = parser.parse_attribute_update(door_closed_msg)
        assert updates["door_state"] == "closed"


class TestDeviceManagerIntegration:
    """Integration tests for device manager with MQTT and WebSocket."""

    @pytest.mark.asyncio
    @patch("ryobi_gdo_2_mqtt.device_manager.Cover")
    @patch("ryobi_gdo_2_mqtt.device_manager.Switch")
    @patch("ryobi_gdo_2_mqtt.device_manager.BinarySensor")
    async def test_device_setup_and_state_sync(
        self, mock_binary_sensor, mock_switch, mock_cover, mock_mqtt_settings, fixtures_dir
    ):
        """Test device setup → MQTT entity creation → state updates from WebSocket."""
        # Setup mocks
        mock_api_client = MagicMock()
        load_fixture(fixtures_dir, "device_update_c4be84986d2e.json")

        async def mock_update_device(device_id):
            from ryobi_gdo_2_mqtt.models import DeviceData

            return DeviceData(door_state="closed", light_state=False, battery_level=0, device_name="Acura")

        mock_api_client.update_device = AsyncMock(side_effect=mock_update_device)
        mock_api_client.get_module = MagicMock(return_value=7)
        mock_api_client.get_module_type = MagicMock(return_value=5)
        mock_api_client._device_modules = {
            "c4be84986d2e": {"garageDoor": "garageDoor_7", "garageLight": "garageLight_7"}
        }

        mock_websocket = MagicMock()
        mock_websocket.send_message = AsyncMock()

        # Create device manager
        device_manager = DeviceManager(mqtt_settings=mock_mqtt_settings, api_client=mock_api_client)
        parser = WebSocketMessageParser()
        device_manager.parser = parser

        # Setup device
        device = await device_manager.setup_device("c4be84986d2e", "Acura", mock_websocket)

        assert device is not None
        assert "c4be84986d2e" in device_manager.devices

        # Verify MQTT entities were created
        assert mock_cover.called
        assert mock_switch.called
        assert mock_binary_sensor.called

        # Simulate WebSocket updates
        light_on_msg = load_fixture(fixtures_dir, "ws_message_1762952732.json")
        await device_manager.handle_device_update("c4be84986d2e", light_on_msg)

        # Cleanup
        await device.cleanup()


class TestCommandFlow:
    """Integration tests for command flow: MQTT → WebSocket → Device."""

    @pytest.mark.asyncio
    @patch("ryobi_gdo_2_mqtt.device_manager.Cover")
    @patch("ryobi_gdo_2_mqtt.device_manager.Switch")
    @patch("ryobi_gdo_2_mqtt.device_manager.BinarySensor")
    async def test_mqtt_command_to_websocket_flow(
        self, mock_binary_sensor, mock_switch, mock_cover, mock_mqtt_settings, fixtures_dir
    ):
        """Test receiving MQTT command → sending WebSocket message → device state update."""
        from paho.mqtt.client import MQTTMessage

        # Setup mocks
        mock_api_client = MagicMock()
        mock_api_client.get_module = MagicMock(return_value=7)
        mock_api_client.get_module_type = MagicMock(return_value=5)

        mock_websocket = MagicMock()
        mock_websocket.send_message = AsyncMock()

        # Get the current event loop
        loop = asyncio.get_running_loop()

        # Create device
        from ryobi_gdo_2_mqtt.device_manager import RyobiDevice

        device = RyobiDevice(
            device_id="c4be84986d2e",
            device_name="Acura",
            mqtt_settings=mock_mqtt_settings,
            websocket=mock_websocket,
            api_client=mock_api_client,
            loop=loop,
        )

        # Simulate MQTT door command
        mqtt_message = MQTTMessage()
        mqtt_message.payload = b"OPEN"

        # Trigger door command handler
        device._handle_door_command(None, None, mqtt_message)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Verify WebSocket message was sent
        mock_websocket.send_message.assert_called_once()
        call_args = mock_websocket.send_message.call_args[0]
        assert call_args[0] == 7  # port_id
        assert call_args[1] == 5  # module_type
        assert call_args[2] == "doorCommand"
        assert call_args[3] == 1  # OPEN command

        # Simulate MQTT light command
        mock_websocket.send_message.reset_mock()
        mqtt_message.payload = b"ON"

        device._handle_light_command(None, None, mqtt_message)
        await asyncio.sleep(0.1)

        # Verify WebSocket message was sent
        mock_websocket.send_message.assert_called_once()
        call_args = mock_websocket.send_message.call_args[0]
        assert call_args[2] == "lightState"
        assert call_args[3] == 1  # ON state


class TestNewEntitiesIntegration:
    """Integration tests for newly added entities."""

    @pytest.mark.asyncio
    @patch("ryobi_gdo_2_mqtt.device_manager.Cover")
    @patch("ryobi_gdo_2_mqtt.device_manager.Switch")
    @patch("ryobi_gdo_2_mqtt.device_manager.BinarySensor")
    @patch("ryobi_gdo_2_mqtt.device_manager.Sensor")
    @patch("ryobi_gdo_2_mqtt.device_manager.Number")
    async def test_all_entities_created_on_device_setup(
        self, mock_number, mock_sensor, mock_binary_sensor, mock_switch, mock_cover, mock_mqtt_settings, fixtures_dir
    ):
        """Test that all entities are created when device is set up."""
        mock_api_client = MagicMock()

        async def mock_update_device(device_id):
            from ryobi_gdo_2_mqtt.models import DeviceData

            return DeviceData(
                door_state="closed",
                light_state=False,
                battery_level=100,
                motion=0,
                wifi_rssi=-50,
                vacation_mode=0,
                park_assist=0,
                inflator=0,
                bt_speaker=0,
                fan=0,
                device_name="Test Device",
            )

        mock_api_client.update_device = AsyncMock(side_effect=mock_update_device)
        mock_api_client.get_module = MagicMock(return_value=7)
        mock_api_client._device_modules = {"test_device": {"garageDoor": "garageDoor_7"}}

        mock_websocket = MagicMock()
        mock_websocket.send_message = AsyncMock()

        from ryobi_gdo_2_mqtt.device_manager import DeviceManager

        device_manager = DeviceManager(mqtt_settings=mock_mqtt_settings, api_client=mock_api_client)

        device = await device_manager.setup_device("test_device", "Test Device", mock_websocket)

        # Verify all entities were created
        assert hasattr(device, "cover")
        assert hasattr(device, "light")
        assert hasattr(device, "battery_sensor")
        assert hasattr(device, "motion_sensor")
        assert hasattr(device, "wifi_sensor")
        assert hasattr(device, "vacation_switch")
        assert hasattr(device, "park_assist_switch")
        assert hasattr(device, "inflator_switch")
        assert hasattr(device, "bt_speaker_switch")
        assert hasattr(device, "fan_number")

    @pytest.mark.asyncio
    async def test_vacation_mode_command_flow(self, mock_mqtt_settings, fixtures_dir):
        """Test vacation mode command flow."""
        from paho.mqtt.client import MQTTMessage

        mock_api_client = MagicMock()
        mock_api_client.get_module = MagicMock(return_value=7)

        mock_websocket = MagicMock()
        mock_websocket.send_message = AsyncMock()

        loop = asyncio.get_running_loop()

        with (
            patch("ryobi_gdo_2_mqtt.device_manager.Cover"),
            patch("ryobi_gdo_2_mqtt.device_manager.Switch"),
            patch("ryobi_gdo_2_mqtt.device_manager.BinarySensor"),
            patch("ryobi_gdo_2_mqtt.device_manager.Sensor"),
            patch("ryobi_gdo_2_mqtt.device_manager.Number"),
        ):
            from ryobi_gdo_2_mqtt.device_manager import RyobiDevice

            device = RyobiDevice(
                device_id="test_device",
                device_name="Test Device",
                mqtt_settings=mock_mqtt_settings,
                websocket=mock_websocket,
                api_client=mock_api_client,
                loop=loop,
            )

            # Simulate MQTT vacation mode command
            mqtt_message = MQTTMessage()
            mqtt_message.payload = b"ON"

            device._handle_vacation_command(None, None, mqtt_message)

            # Wait for async task to complete
            await asyncio.sleep(0.1)

            # Verify WebSocket message was sent
            mock_websocket.send_message.assert_called_once()
            call_args = mock_websocket.send_message.call_args[0]
            assert call_args[2] == "vacationMode"
            assert call_args[3] == 1


class TestEndToEndFlow:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    @patch("ryobi_gdo_2_mqtt.device_manager.Cover")
    @patch("ryobi_gdo_2_mqtt.device_manager.Switch")
    @patch("ryobi_gdo_2_mqtt.device_manager.BinarySensor")
    @patch("ryobi_gdo_2_mqtt.device_manager.Sensor")
    @patch("ryobi_gdo_2_mqtt.device_manager.Number")
    async def test_complete_flow_with_multiple_devices(
        self, mock_number, mock_sensor, mock_binary_sensor, mock_switch, mock_cover, mock_mqtt_settings, fixtures_dir
    ):
        """Test complete flow with multiple devices: auth → discovery → setup → updates."""
        # Mock session
        mock_session = MagicMock(spec=ClientSession)

        # Create API client
        api_client = RyobiApiClient(username="test@example.com", password="testpass", session=mock_session)

        # Mock responses
        login_response = load_fixture(fixtures_dir, "login_response.json")
        devices_response = load_fixture(fixtures_dir, "get_devices_response.json")
        device1_response = load_fixture(fixtures_dir, "device_update_c4be84986d2e.json")
        device2_response = load_fixture(fixtures_dir, "device_update_d4f513e9a416.json")

        async def mock_process_request(url, method, data):
            if "login" in url:
                return login_response
            elif "devices" in url and method == "get":
                if "c4be84986d2e" in url:
                    return device1_response
                elif "d4f513e9a416" in url:
                    return device2_response
                return devices_response
            return None

        api_client._process_request = AsyncMock(side_effect=mock_process_request)

        # Step 1: Authenticate
        await api_client.get_api_key()
        assert api_client.api_key == "1234567890"

        # Step 2: Discover devices
        devices = await api_client.get_devices()
        assert len(devices) == 2

        # Step 3: Setup device manager
        device_manager = DeviceManager(mqtt_settings=mock_mqtt_settings, api_client=api_client)
        parser = WebSocketMessageParser()
        device_manager.parser = parser

        # Step 4: Setup all devices
        mock_websocket1 = MagicMock()
        mock_websocket1.send_message = AsyncMock()
        mock_websocket2 = MagicMock()
        mock_websocket2.send_message = AsyncMock()

        device1 = await device_manager.setup_device("c4be84986d2e", "Acura", mock_websocket1)
        device2 = await device_manager.setup_device("d4f513e9a416", "Genesis", mock_websocket2)

        assert len(device_manager.devices) == 2
        assert device1 is not None
        assert device2 is not None

        # Step 5: Simulate WebSocket updates for both devices
        light_msg = load_fixture(fixtures_dir, "ws_message_1762952732.json")
        await device_manager.handle_device_update("c4be84986d2e", light_msg)

        # Verify both devices are independently managed
        assert "c4be84986d2e" in device_manager.devices
        assert "d4f513e9a416" in device_manager.devices
