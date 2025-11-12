import ssl
from unittest.mock import AsyncMock, MagicMock

import certifi
import pytest
from aiohttp import ClientSession, TCPConnector

from ryobi_gdo_2_mqtt.api import RyobiApiClient


@pytest.mark.asyncio
async def test_get_api_key_with_real_session():
    """Test API key retrieval with a real aiohttp session."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = TCPConnector(ssl=ssl_context)
    async with ClientSession(connector=connector) as session:
        client = RyobiApiClient(username="sincore@gmail.com", password="613I0yoVL12", session=session)

        result = await client.get_api_key()

        assert result is True


@pytest.mark.asyncio
async def test_get_devices_with_real_session():
    """Test device retrieval with a real aiohttp session."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = TCPConnector(ssl=ssl_context)
    async with ClientSession(connector=connector) as session:
        client = RyobiApiClient(username="sincore@gmail.com", password="613I0yoVL12", session=session)

        devices = await client.get_devices()
        print(devices)

        assert 1 == 2
        assert isinstance(devices, dict)
        assert len(devices) > 0


@pytest.mark.asyncio
async def test_get_api_key_success():
    """Test successful API key retrieval."""
    session = MagicMock(spec=ClientSession)
    client = RyobiApiClient(username="test@example.com", password="testpass", device_id="device123", session=session)

    mock_response = {"result": {"metaData": {"wskAuthAttempts": [{"apiKey": "test_api_key_123"}]}}}

    client._process_request = AsyncMock(return_value=mock_response)

    result = await client.get_api_key()

    assert result is True
    assert client.api_key == "test_api_key_123"


@pytest.mark.asyncio
async def test_get_api_key_failure():
    """Test API key retrieval failure."""
    session = MagicMock(spec=ClientSession)
    client = RyobiApiClient(username="test@example.com", password="testpass", device_id="device123", session=session)

    client._process_request = AsyncMock(return_value=None)

    result = await client.get_api_key()

    assert result is False
    assert client.api_key is None


@pytest.mark.asyncio
async def test_get_api_key_invalid_response():
    """Test API key retrieval with invalid response format."""
    session = MagicMock(spec=ClientSession)
    client = RyobiApiClient(username="test@example.com", password="testpass", device_id="device123", session=session)

    mock_response = {"result": {}}

    client._process_request = AsyncMock(return_value=mock_response)

    result = await client.get_api_key()

    assert result is False
    assert client.api_key is None
