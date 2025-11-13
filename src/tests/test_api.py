"""Tests for Ryobi API client."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientSession

from ryobi_gdo_2_mqtt.api import RyobiApiClient
from ryobi_gdo_2_mqtt.exceptions import RyobiAuthenticationError, RyobiDeviceNotFoundError, RyobiInvalidResponseError
from tests.conftest import load_fixture


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    return MagicMock(spec=ClientSession)


@pytest.fixture
def api_client(mock_session):
    """Create an API client with mocked session."""
    return RyobiApiClient(username="test@example.com", password="testpass", session=mock_session)


class TestRyobiApiClient:
    """Tests for RyobiApiClient."""

    @pytest.mark.asyncio
    async def test_get_api_key_success(self, api_client, fixtures_dir):
        """Test successful API key retrieval."""
        mock_response = load_fixture(fixtures_dir, "login_response.json")
        api_client._process_request = AsyncMock(return_value=mock_response)

        result = await api_client.get_api_key()

        assert result is True
        assert api_client.api_key == "1234567890"

    @pytest.mark.asyncio
    async def test_get_api_key_failure_no_response(self, api_client):
        """Test API key retrieval when no response received."""
        api_client._process_request = AsyncMock(return_value=None)

        with pytest.raises(RyobiAuthenticationError, match="Failed to get response from login endpoint"):
            await api_client.get_api_key()

    @pytest.mark.asyncio
    async def test_get_api_key_invalid_response_format(self, api_client):
        """Test API key retrieval with invalid response format."""
        mock_response = {"result": {}}
        api_client._process_request = AsyncMock(return_value=mock_response)

        with pytest.raises(RyobiInvalidResponseError):
            await api_client.get_api_key()

    @pytest.mark.asyncio
    async def test_get_devices_success(self, api_client, fixtures_dir):
        """Test successful device retrieval."""
        mock_response = load_fixture(fixtures_dir, "get_devices_response.json")
        api_client._process_request = AsyncMock(return_value=mock_response)

        devices = await api_client.get_devices()

        assert isinstance(devices, dict)
        assert len(devices) == 2
        assert devices["c4be84986d2e"] == "Acura"
        assert devices["d4f513e9a416"] == "Genesis"

    @pytest.mark.asyncio
    async def test_get_devices_empty_result(self, api_client):
        """Test device retrieval with empty result."""
        mock_response = {"result": []}
        api_client._process_request = AsyncMock(return_value=mock_response)

        with pytest.raises(RyobiDeviceNotFoundError):
            await api_client.get_devices()

    @pytest.mark.asyncio
    async def test_update_device_success(self, api_client, fixtures_dir):
        """Test successful device update."""
        mock_response = load_fixture(fixtures_dir, "device_update_c4be84986d2e.json")
        api_client._process_request = AsyncMock(return_value=mock_response)

        device_data = await api_client.update_device("c4be84986d2e")

        assert device_data is not None
        assert device_data.door_state == "closed"
        assert device_data.light_state is False
        assert device_data.battery_level == 0
        assert device_data.device_name == "Acura"

    @pytest.mark.asyncio
    async def test_update_device_indexes_modules(self, api_client, fixtures_dir):
        """Test that update_device correctly indexes modules."""
        mock_response = load_fixture(fixtures_dir, "device_update_c4be84986d2e.json")
        api_client._process_request = AsyncMock(return_value=mock_response)

        await api_client.update_device("c4be84986d2e")

        # Check that modules were indexed
        assert "c4be84986d2e" in api_client._device_modules
        modules = api_client._device_modules["c4be84986d2e"]
        assert "garageDoor" in modules
        assert "garageLight" in modules
        assert "backupCharger" in modules
        assert "wifiModule" in modules

    @pytest.mark.asyncio
    async def test_get_module_returns_port_id(self, api_client, fixtures_dir):
        """Test getting module port ID."""
        mock_response = load_fixture(fixtures_dir, "device_update_c4be84986d2e.json")
        api_client._process_request = AsyncMock(return_value=mock_response)
        await api_client.update_device("c4be84986d2e")

        port_id = api_client.get_module("c4be84986d2e", "garageDoor")

        assert port_id == 7

    @pytest.mark.asyncio
    async def test_get_module_returns_none_for_unknown_device(self, api_client):
        """Test getting module for unknown device returns None."""
        port_id = api_client.get_module("unknown_device", "garageDoor")

        assert port_id is None

    @pytest.mark.asyncio
    async def test_get_module_returns_none_for_unknown_module(self, api_client, fixtures_dir):
        """Test getting unknown module returns None."""
        mock_response = load_fixture(fixtures_dir, "device_update_c4be84986d2e.json")
        api_client._process_request = AsyncMock(return_value=mock_response)
        await api_client.update_device("c4be84986d2e")

        port_id = api_client.get_module("c4be84986d2e", "unknownModule")

        assert port_id is None

    def test_get_module_type_returns_correct_type(self, api_client):
        """Test getting module type ID."""
        assert api_client.get_module_type("garageDoor") == 5
        assert api_client.get_module_type("backupCharger") == 6
        assert api_client.get_module_type("garageLight") == 5
        assert api_client.get_module_type("wifiModule") == 7

    def test_get_module_type_returns_none_for_unknown(self, api_client):
        """Test getting unknown module type returns None."""
        assert api_client.get_module_type("unknownModule") is None


class TestApiClientModuleConfig:
    """Tests for API client module configuration integration."""

    def test_get_module_type_uses_modules_config(self, api_client):
        """Test that get_module_type uses MODULES configuration."""
        from ryobi_gdo_2_mqtt.device_manager import MODULES

        for module_name, config in MODULES.items():
            module_type = api_client.get_module_type(module_name)
            assert module_type == config.module_type

    def test_get_module_type_returns_none_for_unknown_module(self, api_client):
        """Test that get_module_type returns None for unknown modules."""
        assert api_client.get_module_type("unknownModule") is None
