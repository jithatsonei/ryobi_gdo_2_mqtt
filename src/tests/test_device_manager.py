"""Tests for device manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ryobi_gdo_2_mqtt.device_manager import DeviceManager, RyobiDevice
from tests.conftest import load_fixture


@pytest.fixture
def mock_mqtt_settings():
    """Create mock MQTT settings."""
    from ha_mqtt_discoverable import Settings as MQTTSettings

    return MQTTSettings.MQTT(host="localhost", port=1883)


@pytest.fixture
def mock_api_client():
    """Create mock API client."""
    client = MagicMock()
    client.get_module = MagicMock(return_value=7)
    client.get_module_type = MagicMock(return_value=5)
    return client


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket."""
    ws = MagicMock()
    ws.send_message = AsyncMock()
    return ws


@pytest.fixture
def device_manager(mock_mqtt_settings, mock_api_client):
    """Create a device manager instance."""
    return DeviceManager(mqtt_settings=mock_mqtt_settings, api_client=mock_api_client)


class TestRyobiDevice:
    """Tests for RyobiDevice."""

    @patch("ryobi_gdo_2_mqtt.device_manager.Cover")
    @patch("ryobi_gdo_2_mqtt.device_manager.Switch")
    @patch("ryobi_gdo_2_mqtt.device_manager.BinarySensor")
    def test_device_initialization(
        self, mock_binary_sensor, mock_switch, mock_cover, mock_mqtt_settings, mock_websocket, mock_api_client
    ):
        """Test device initialization creates all entities."""
        import asyncio

        loop = asyncio.new_event_loop()

        device = RyobiDevice(
            device_id="test_device",
            device_name="Test Device",
            mqtt_settings=mock_mqtt_settings,
            websocket=mock_websocket,
            api_client=mock_api_client,
            loop=loop,
        )

        assert device.device_id == "test_device"
        assert device.device_name == "Test Device"
        assert mock_cover.called
        assert mock_switch.called
        assert mock_binary_sensor.called

        loop.close()

    @patch("ryobi_gdo_2_mqtt.device_manager.Cover")
    @patch("ryobi_gdo_2_mqtt.device_manager.Switch")
    @patch("ryobi_gdo_2_mqtt.device_manager.BinarySensor")
    def test_update_door_state(
        self, mock_binary_sensor, mock_switch, mock_cover, mock_mqtt_settings, mock_websocket, mock_api_client
    ):
        """Test updating door state."""
        import asyncio

        loop = asyncio.new_event_loop()

        mock_cover_instance = MagicMock()
        mock_cover.return_value = mock_cover_instance

        device = RyobiDevice(
            device_id="test_device",
            device_name="Test Device",
            mqtt_settings=mock_mqtt_settings,
            websocket=mock_websocket,
            api_client=mock_api_client,
            loop=loop,
        )

        # Reset mock after initialization
        mock_cover_instance.reset_mock()

        device.update_door_state("open")
        mock_cover_instance.open.assert_called_once()

        device.update_door_state("closed")
        mock_cover_instance.closed.assert_called_once()

        loop.close()

    @patch("ryobi_gdo_2_mqtt.device_manager.Cover")
    @patch("ryobi_gdo_2_mqtt.device_manager.Switch")
    @patch("ryobi_gdo_2_mqtt.device_manager.BinarySensor")
    def test_update_light_state(
        self, mock_binary_sensor, mock_switch, mock_cover, mock_mqtt_settings, mock_websocket, mock_api_client
    ):
        """Test updating light state."""
        import asyncio

        loop = asyncio.new_event_loop()

        mock_switch_instance = MagicMock()
        mock_switch.return_value = mock_switch_instance

        device = RyobiDevice(
            device_id="test_device",
            device_name="Test Device",
            mqtt_settings=mock_mqtt_settings,
            websocket=mock_websocket,
            api_client=mock_api_client,
            loop=loop,
        )

        # Reset mock after initialization
        mock_switch_instance.reset_mock()

        device.update_light_state(True)
        mock_switch_instance.on.assert_called_once()

        device.update_light_state(False)
        mock_switch_instance.off.assert_called_once()

        loop.close()

    @patch("ryobi_gdo_2_mqtt.device_manager.Cover")
    @patch("ryobi_gdo_2_mqtt.device_manager.Switch")
    @patch("ryobi_gdo_2_mqtt.device_manager.BinarySensor")
    def test_update_battery_level(
        self, mock_binary_sensor, mock_switch, mock_cover, mock_mqtt_settings, mock_websocket, mock_api_client
    ):
        """Test updating battery level."""
        import asyncio

        loop = asyncio.new_event_loop()

        mock_battery_instance = MagicMock()
        mock_binary_sensor.return_value = mock_battery_instance

        device = RyobiDevice(
            device_id="test_device",
            device_name="Test Device",
            mqtt_settings=mock_mqtt_settings,
            websocket=mock_websocket,
            api_client=mock_api_client,
            loop=loop,
        )

        # Low battery
        device.update_battery_level(15)
        mock_battery_instance.on.assert_called_once()

        # Normal battery
        device.update_battery_level(75)
        mock_battery_instance.off.assert_called_once()

        loop.close()


class TestModuleConfig:
    """Tests for ModuleConfig and MODULES configuration."""

    def test_module_config_dataclass(self):
        """Test ModuleConfig dataclass creation."""
        from ryobi_gdo_2_mqtt.device_manager import ModuleConfig

        config = ModuleConfig(
            name="testModule",
            module_type=5,
            attribute_name="testAttribute",
        )

        assert config.name == "testModule"
        assert config.module_type == 5
        assert config.attribute_name == "testAttribute"

    def test_all_modules_defined(self):
        """Test that all expected modules are defined in MODULES."""
        from ryobi_gdo_2_mqtt.device_manager import MODULES

        expected_modules = [
            "garageDoor",
            "garageLight",
            "backupCharger",
            "wifiModule",
            "parkAssistLaser",
            "inflator",
            "btSpeaker",
            "fan",
        ]

        for module in expected_modules:
            assert module in MODULES, f"Module {module} not found in MODULES"

    def test_module_config_has_required_fields(self):
        """Test that all module configs have required fields."""
        from ryobi_gdo_2_mqtt.device_manager import MODULES

        for module_name, config in MODULES.items():
            assert config.name == module_name
            assert isinstance(config.module_type, int)
            assert isinstance(config.attribute_name, str)
            assert config.module_type > 0

    def test_module_types_are_unique_per_module(self):
        """Test that module types are consistent."""
        from ryobi_gdo_2_mqtt.device_manager import MODULES

        # Some modules can share types (e.g., garageDoor and garageLight both use type 5)
        # but each module should have a consistent type
        assert MODULES["garageDoor"].module_type == 5
        assert MODULES["garageLight"].module_type == 5
        assert MODULES["backupCharger"].module_type == 6
        assert MODULES["wifiModule"].module_type == 7
        assert MODULES["parkAssistLaser"].module_type == 1
        assert MODULES["inflator"].module_type == 4
        assert MODULES["btSpeaker"].module_type == 2
        assert MODULES["fan"].module_type == 3


class TestCommandHandler:
    """Tests for CommandHandler."""

    @pytest.fixture
    def mock_device(self, mock_mqtt_settings, mock_websocket, mock_api_client):
        """Create a mock device for testing."""
        import asyncio

        loop = asyncio.new_event_loop()

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

        yield device
        loop.close()

    def test_command_handler_initialization(self, mock_device):
        """Test CommandHandler initialization."""
        from ryobi_gdo_2_mqtt.device_manager import CommandHandler

        handler = CommandHandler(mock_device)

        assert handler.device is mock_device

    def test_send_command_with_default_attribute(self, mock_device):
        """Test sending command with default attribute from module config."""
        mock_device.api_client.get_module.return_value = 7
        mock_device.websocket.send_message = AsyncMock()

        mock_device.command_handler.send_command("garageDoor", 1)

        # Should use default attribute "doorCommand" from MODULES config
        mock_device.websocket.send_message.assert_called_once()

    def test_send_command_with_custom_attribute(self, mock_device):
        """Test sending command with custom attribute override."""
        mock_device.api_client.get_module.return_value = 7
        mock_device.websocket.send_message = AsyncMock()

        mock_device.command_handler.send_command("garageDoor", 1, "customAttribute")

        # Should use custom attribute instead of default
        mock_device.websocket.send_message.assert_called_once()

    def test_send_command_unknown_module(self, mock_device):
        """Test sending command to unknown module logs error."""
        with patch("ryobi_gdo_2_mqtt.device_manager.log") as mock_log:
            mock_device.command_handler.send_command("unknownModule", 1)

            mock_log.error.assert_called_once()
            assert "Unknown module" in str(mock_log.error.call_args)

    def test_send_command_module_not_available(self, mock_device):
        """Test sending command when module info not available."""
        mock_device.api_client.get_module.return_value = None

        with patch("ryobi_gdo_2_mqtt.device_manager.log") as mock_log:
            mock_device.command_handler.send_command("garageDoor", 1)

            mock_log.error.assert_called_once()
            assert "module info not available" in str(mock_log.error.call_args)


class TestEntityFactory:
    """Tests for EntityFactory."""

    @pytest.fixture
    def device_info(self):
        """Create device info for testing."""
        from ha_mqtt_discoverable import DeviceInfo

        return DeviceInfo(
            name="Test Device",
            identifiers="test_device",
            manufacturer="Ryobi",
            model="Garage Door Opener",
        )

    def test_create_cover(self, mock_mqtt_settings, device_info):
        """Test creating a cover entity."""
        from ryobi_gdo_2_mqtt.device_manager import EntityFactory

        callback = MagicMock()

        with patch("ryobi_gdo_2_mqtt.device_manager.Cover") as mock_cover:
            cover = EntityFactory.create_cover("test_device", "Test Device", device_info, mock_mqtt_settings, callback)

            mock_cover.assert_called_once()
            assert cover is not None

    def test_create_switch(self, mock_mqtt_settings, device_info):
        """Test creating a switch entity."""
        from ryobi_gdo_2_mqtt.device_manager import EntityFactory

        callback = MagicMock()

        with patch("ryobi_gdo_2_mqtt.device_manager.Switch") as mock_switch:
            switch = EntityFactory.create_switch(
                "test_device", "Test Device", device_info, mock_mqtt_settings, callback, "light"
            )

            mock_switch.assert_called_once()
            assert switch is not None

    def test_create_binary_sensor(self, mock_mqtt_settings, device_info):
        """Test creating a binary sensor entity."""
        from ryobi_gdo_2_mqtt.device_manager import EntityFactory

        with patch("ryobi_gdo_2_mqtt.device_manager.BinarySensor") as mock_sensor:
            sensor = EntityFactory.create_binary_sensor(
                "test_device", "Test Device", device_info, mock_mqtt_settings, "battery"
            )

            mock_sensor.assert_called_once()
            assert sensor is not None

    def test_create_sensor(self, mock_mqtt_settings, device_info):
        """Test creating a sensor entity."""
        from ryobi_gdo_2_mqtt.device_manager import EntityFactory

        with patch("ryobi_gdo_2_mqtt.device_manager.Sensor") as mock_sensor:
            sensor = EntityFactory.create_sensor(
                "test_device", "Test Device", device_info, mock_mqtt_settings, "wifi", "signal_strength", "dBm"
            )

            mock_sensor.assert_called_once()
            assert sensor is not None

    def test_create_number(self, mock_mqtt_settings, device_info):
        """Test creating a number entity."""
        from ryobi_gdo_2_mqtt.device_manager import EntityFactory

        callback = MagicMock()

        with patch("ryobi_gdo_2_mqtt.device_manager.Number") as mock_number:
            number = EntityFactory.create_number(
                "test_device", "Test Device", device_info, mock_mqtt_settings, callback, "fan"
            )

            mock_number.assert_called_once()
            assert number is not None

    def test_switch_entity_types(self, mock_mqtt_settings, device_info):
        """Test all switch entity types can be created."""
        from ryobi_gdo_2_mqtt.device_manager import EntityFactory

        callback = MagicMock()
        entity_types = ["light", "vacation", "park_assist", "inflator", "bt_speaker"]

        with patch("ryobi_gdo_2_mqtt.device_manager.Switch"):
            for entity_type in entity_types:
                switch = EntityFactory.create_switch(
                    "test_device", "Test Device", device_info, mock_mqtt_settings, callback, entity_type
                )
                assert switch is not None


class TestDeviceManager:
    """Tests for DeviceManager."""

    @pytest.mark.asyncio
    async def test_setup_device_success(self, device_manager, mock_websocket, fixtures_dir):
        """Test successful device setup."""
        device_manager.api_client.update_device = AsyncMock(
            return_value=MagicMock(door_state="closed", light_state=False, battery_level=0)
        )

        with patch("ryobi_gdo_2_mqtt.device_manager.RyobiDevice") as mock_device_class:
            mock_device = MagicMock()
            mock_device_class.return_value = mock_device

            device = await device_manager.setup_device("c4be84986d2e", "Acura", mock_websocket)

            assert device is not None
            assert "c4be84986d2e" in device_manager.devices

    @pytest.mark.asyncio
    async def test_setup_device_failure(self, device_manager, mock_websocket):
        """Test device setup failure."""
        device_manager.api_client.update_device = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Failed to get initial state"):
            await device_manager.setup_device("bad_device", "Bad Device", mock_websocket)

    @pytest.mark.asyncio
    async def test_handle_device_update(self, device_manager, fixtures_dir):
        """Test handling device updates from WebSocket."""
        # Setup a device first
        mock_device = MagicMock()
        mock_device.update_door_state = MagicMock()
        mock_device.update_light_state = MagicMock()
        device_manager.devices["c4be84986d2e"] = mock_device

        # Setup parser
        mock_parser = MagicMock()
        mock_parser.parse_attribute_update = MagicMock(return_value={"door_state": "open", "light_state": True})
        device_manager.parser = mock_parser

        # Handle update
        ws_data = load_fixture(fixtures_dir, "ws_message_1762952771.json")
        await device_manager.handle_device_update("c4be84986d2e", ws_data)

        mock_device.update_door_state.assert_called_once_with("open")
        mock_device.update_light_state.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_handle_device_update_unknown_device(self, device_manager, fixtures_dir):
        """Test handling update for unknown device."""
        ws_data = load_fixture(fixtures_dir, "ws_message_1762952771.json")

        # Should not raise, just log warning
        await device_manager.handle_device_update("unknown_device", ws_data)
