"""Tests for RyobiGDO2MQTT main application classes."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientSession

from ryobi_gdo_2_mqtt.exceptions import RyobiApiError
from ryobi_gdo_2_mqtt.ryobigdo2mqtt import ApplicationBootstrap, ResourceManager, ServiceRunner
from ryobi_gdo_2_mqtt.settings import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    with patch.dict("os.environ", {}, clear=False):
        return Settings(
            email="test@example.com",
            password="testpass",
            mqtt_host="localhost",
            mqtt_port=1883,
            mqtt_user="mqttuser",
            mqtt_password="mqttpass",
            log_level="INFO",
            _cli_parse_args=False,
        )


class TestResourceManager:
    """Tests for ResourceManager."""

    def test_initialization(self):
        """Test resource manager initialization."""
        manager = ResourceManager()

        assert manager._tasks == set()
        assert manager.session is None
        assert manager.coordinator is None
        assert not manager._shutdown_event.is_set()

    def test_add_task(self):
        """Test adding a task to be managed."""
        manager = ResourceManager()
        mock_task = MagicMock(spec=asyncio.Task)

        manager.add_task(mock_task)

        assert mock_task in manager._tasks
        mock_task.add_done_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_cancels_tasks(self):
        """Test cleanup cancels all tasks."""
        manager = ResourceManager()

        # Create mock tasks
        mock_task1 = MagicMock(spec=asyncio.Task)
        mock_task1.done.return_value = False
        mock_task2 = MagicMock(spec=asyncio.Task)
        mock_task2.done.return_value = False

        manager._tasks = {mock_task1, mock_task2}

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            await manager.cleanup()

            mock_task1.cancel.assert_called_once()
            mock_task2.cancel.assert_called_once()
            mock_gather.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_closes_session(self):
        """Test cleanup closes the session."""
        manager = ResourceManager()
        mock_session = MagicMock(spec=ClientSession)
        mock_session.closed = False
        mock_session.close = AsyncMock()
        manager.session = mock_session

        await manager.cleanup()

        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_cleans_coordinator(self):
        """Test cleanup calls coordinator cleanup."""
        manager = ResourceManager()
        mock_coordinator = MagicMock()
        mock_coordinator.cleanup = AsyncMock()
        manager.coordinator = mock_coordinator

        await manager.cleanup()

        mock_coordinator.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_sets_shutdown_event(self):
        """Test cleanup sets the shutdown event."""
        manager = ResourceManager()

        await manager.cleanup()

        assert manager._shutdown_event.is_set()


class TestApplicationBootstrap:
    """Tests for ApplicationBootstrap."""

    def test_initialization(self, mock_settings):
        """Test bootstrap initialization."""
        bootstrap = ApplicationBootstrap(mock_settings)

        assert bootstrap.settings is mock_settings
        assert bootstrap.api_client is None
        assert bootstrap.mqtt_settings is None
        assert bootstrap.parser is None
        assert bootstrap.device_manager is None
        assert bootstrap.coordinator is None

    def test_configure_logging(self, mock_settings):
        """Test logging configuration."""
        bootstrap = ApplicationBootstrap(mock_settings)

        with patch("ryobi_gdo_2_mqtt.ryobigdo2mqtt.log") as mock_log:
            bootstrap.configure_logging()

            mock_log.setLevel.assert_called_once()
            mock_log.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_session(self, mock_settings):
        """Test session initialization."""
        bootstrap = ApplicationBootstrap(mock_settings)

        with (
            patch("ryobi_gdo_2_mqtt.ryobigdo2mqtt.ssl.create_default_context") as mock_ssl,
            patch("ryobi_gdo_2_mqtt.ryobigdo2mqtt.TCPConnector") as mock_connector,
            patch("ryobi_gdo_2_mqtt.ryobigdo2mqtt.aiohttp.ClientSession") as mock_session,
        ):
            session = await bootstrap.initialize_session()

            mock_ssl.assert_called_once()
            mock_connector.assert_called_once()
            mock_session.assert_called_once()
            assert session is not None

    @pytest.mark.asyncio
    async def test_authenticate_success(self, mock_settings):
        """Test successful authentication."""
        bootstrap = ApplicationBootstrap(mock_settings)
        mock_session = MagicMock(spec=ClientSession)

        with patch("ryobi_gdo_2_mqtt.ryobigdo2mqtt.RyobiApiClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get_api_key = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_client

            await bootstrap.authenticate(mock_session)

            assert bootstrap.api_client is mock_client
            mock_client.get_api_key.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, mock_settings):
        """Test authentication failure exits."""
        bootstrap = ApplicationBootstrap(mock_settings)
        mock_session = MagicMock(spec=ClientSession)

        with (
            patch("ryobi_gdo_2_mqtt.ryobigdo2mqtt.RyobiApiClient") as mock_client_class,
            pytest.raises(SystemExit),
        ):
            mock_client = MagicMock()
            mock_client.get_api_key = AsyncMock(side_effect=RyobiApiError("Auth failed"))
            mock_client_class.return_value = mock_client

            await bootstrap.authenticate(mock_session)

    @pytest.mark.asyncio
    async def test_discover_devices_success(self, mock_settings):
        """Test successful device discovery."""
        bootstrap = ApplicationBootstrap(mock_settings)
        bootstrap.api_client = MagicMock()
        bootstrap.api_client.get_devices = AsyncMock(return_value={"device1": "Device 1", "device2": "Device 2"})

        devices = await bootstrap.discover_devices()

        assert len(devices) == 2
        assert "device1" in devices
        assert devices["device1"] == "Device 1"

    @pytest.mark.asyncio
    async def test_discover_devices_failure(self, mock_settings):
        """Test device discovery failure exits."""
        bootstrap = ApplicationBootstrap(mock_settings)
        bootstrap.api_client = MagicMock()
        bootstrap.api_client.get_devices = AsyncMock(side_effect=RyobiApiError("Discovery failed"))

        with pytest.raises(SystemExit):
            await bootstrap.discover_devices()

    def test_initialize_mqtt(self, mock_settings):
        """Test MQTT initialization."""
        bootstrap = ApplicationBootstrap(mock_settings)

        with patch("ryobi_gdo_2_mqtt.ryobigdo2mqtt.MQTTSettings") as mock_mqtt_settings:
            bootstrap.initialize_mqtt()

            mock_mqtt_settings.MQTT.assert_called_once_with(
                host="localhost", port=1883, username="mqttuser", password="mqttpass"
            )
            assert bootstrap.mqtt_settings is not None

    def test_initialize_components(self, mock_settings):
        """Test component initialization."""
        bootstrap = ApplicationBootstrap(mock_settings)
        bootstrap.mqtt_settings = MagicMock()
        bootstrap.api_client = MagicMock()

        with (
            patch("ryobi_gdo_2_mqtt.ryobigdo2mqtt.WebSocketMessageParser") as mock_parser,
            patch("ryobi_gdo_2_mqtt.ryobigdo2mqtt.DeviceManager") as mock_device_manager,
            patch("ryobi_gdo_2_mqtt.ryobigdo2mqtt.ServiceCoordinator") as mock_coordinator,
        ):
            bootstrap.initialize_components()

            mock_parser.assert_called_once()
            mock_device_manager.assert_called_once()
            mock_coordinator.assert_called_once()
            assert bootstrap.parser is not None
            assert bootstrap.device_manager is not None
            assert bootstrap.coordinator is not None


class TestServiceRunner:
    """Tests for ServiceRunner."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        return MagicMock()

    @pytest.fixture
    def mock_resource_manager(self):
        """Create mock resource manager."""
        manager = MagicMock(spec=ResourceManager)
        manager._tasks = set()
        manager.add_task = MagicMock()
        manager.cleanup = AsyncMock()
        return manager

    @pytest.fixture
    def service_runner(self, mock_coordinator, mock_resource_manager):
        """Create service runner instance."""
        return ServiceRunner(coordinator=mock_coordinator, resource_manager=mock_resource_manager)

    def test_initialization(self, service_runner, mock_coordinator, mock_resource_manager):
        """Test service runner initialization."""
        assert service_runner.coordinator is mock_coordinator
        assert service_runner.resource_manager is mock_resource_manager

    @pytest.mark.asyncio
    async def test_setup_devices_success(self, service_runner, mock_coordinator, mock_resource_manager):
        """Test successful device setup."""
        devices = {"device1": "Device 1", "device2": "Device 2"}
        mock_session = MagicMock(spec=ClientSession)

        mock_ws1 = MagicMock()
        mock_ws1.listen = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.listen = AsyncMock()

        mock_coordinator.setup_device = AsyncMock(side_effect=[mock_ws1, mock_ws2])

        with patch("asyncio.create_task") as mock_create_task:
            mock_task1 = MagicMock(spec=asyncio.Task)
            mock_task2 = MagicMock(spec=asyncio.Task)
            mock_create_task.side_effect = [mock_task1, mock_task2]

            await service_runner.setup_devices(devices, "user@example.com", "apikey123", mock_session)

            assert mock_coordinator.setup_device.call_count == 2
            assert mock_resource_manager.add_task.call_count == 2

    @pytest.mark.asyncio
    async def test_setup_devices_handles_failure(self, service_runner, mock_coordinator, mock_resource_manager):
        """Test device setup handles failures gracefully."""
        devices = {"device1": "Device 1", "device2": "Device 2"}
        mock_session = MagicMock(spec=ClientSession)

        mock_ws = MagicMock()
        mock_ws.listen = AsyncMock()

        # First device fails, second succeeds
        mock_coordinator.setup_device = AsyncMock(side_effect=[ValueError("Setup failed"), mock_ws])

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock(spec=asyncio.Task)
            mock_create_task.return_value = mock_task

            await service_runner.setup_devices(devices, "user@example.com", "apikey123", mock_session)

            # Should only add task for successful device
            assert mock_resource_manager.add_task.call_count == 1

    @pytest.mark.asyncio
    async def test_run_gathers_tasks(self, service_runner, mock_resource_manager):
        """Test run gathers all tasks."""
        mock_task1 = MagicMock(spec=asyncio.Task)
        mock_task2 = MagicMock(spec=asyncio.Task)
        mock_resource_manager._tasks = {mock_task1, mock_task2}

        with patch("asyncio.gather") as mock_gather:
            mock_gather.return_value = asyncio.Future()
            mock_gather.return_value.set_result(None)

            await service_runner.run()

            mock_gather.assert_called_once()
            call_args = mock_gather.call_args[0]
            assert mock_task1 in call_args
            assert mock_task2 in call_args

    @pytest.mark.asyncio
    async def test_run_handles_cancellation(self, service_runner, mock_resource_manager):
        """Test run handles cancellation gracefully."""
        mock_resource_manager._tasks = set()

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            mock_gather.side_effect = asyncio.CancelledError()

            await service_runner.run()

            mock_resource_manager.cleanup.assert_called_once()
