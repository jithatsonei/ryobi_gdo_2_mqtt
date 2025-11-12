import asyncio
import logging
import ssl
import sys

import aiohttp
import certifi
from aiohttp import TCPConnector
from ha_mqtt_discoverable import Settings as MQTTSettings

from ryobi_gdo_2_mqtt.api import RyobiApiClient
from ryobi_gdo_2_mqtt.device_manager import DeviceManager
from ryobi_gdo_2_mqtt.exceptions import RyobiApiError
from ryobi_gdo_2_mqtt.logging import log
from ryobi_gdo_2_mqtt.service import ServiceCoordinator
from ryobi_gdo_2_mqtt.settings import Settings
from ryobi_gdo_2_mqtt.websocket_parser import WebSocketMessageParser


class ResourceManager:
    """Manages cleanup of application resources."""

    def __init__(self):
        """Initialize the resource manager."""
        self._tasks: set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        self.session: aiohttp.ClientSession | None = None
        self.coordinator: ServiceCoordinator | None = None

    def add_task(self, task: asyncio.Task) -> None:
        """Add a task to be managed.

        Args:
            task: The task to manage
        """
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def cleanup(self) -> None:
        """Clean up all managed resources."""
        log.info("Cleaning up resources...")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Clean up coordinator
        if self.coordinator:
            await self.coordinator.cleanup()

        # Close session
        if self.session and not self.session.closed:
            await self.session.close()


class ApplicationBootstrap:
    """Handles application initialization."""

    def __init__(self, settings: Settings):
        """Initialize the bootstrap.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.api_client: RyobiApiClient | None = None
        self.mqtt_settings: MQTTSettings.MQTT | None = None
        self.parser: WebSocketMessageParser | None = None
        self.device_manager: DeviceManager | None = None
        self.coordinator: ServiceCoordinator | None = None

    def configure_logging(self) -> None:
        """Configure application logging."""
        log_level = getattr(logging, self.settings.log_level.upper(), logging.INFO)
        log.setLevel(log_level)

        # Also set for ha-mqtt-discoverable and paho
        logging.getLogger("ha_mqtt_discoverable").setLevel(log_level)
        logging.getLogger("paho.mqtt.client").setLevel(log_level)

        log.info("Log level set to: %s", self.settings.log_level)

    async def initialize_session(self) -> aiohttp.ClientSession:
        """Initialize aiohttp session.

        Returns:
            Configured ClientSession
        """
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = TCPConnector(ssl=ssl_context)
        return aiohttp.ClientSession(connector=connector)

    async def authenticate(self, session: aiohttp.ClientSession) -> None:
        """Authenticate with Ryobi API.

        Args:
            session: aiohttp ClientSession

        Raises:
            SystemExit: If authentication fails
        """
        self.api_client = RyobiApiClient(
            username=self.settings.email,
            password=self.settings.password.get_secret_value(),
            session=session,
        )

        log.info("Authenticating with Ryobi API...")
        try:
            await self.api_client.get_api_key()
            log.info("Successfully authenticated with Ryobi API")
        except RyobiApiError as e:
            log.error("Failed to authenticate with Ryobi API: %s", e)
            sys.exit(1)

    async def discover_devices(self) -> dict[str, str]:
        """Discover all devices.

        Returns:
            Dictionary of device_id -> device_name

        Raises:
            SystemExit: If device discovery fails
        """
        log.info("Fetching all devices...")
        try:
            all_devices = await self.api_client.get_devices()
            log.info("Found devices: %s", all_devices)
            return all_devices
        except RyobiApiError as e:
            log.error("Failed to get devices: %s", e)
            sys.exit(1)

    def initialize_mqtt(self) -> None:
        """Initialize MQTT settings."""
        self.mqtt_settings = MQTTSettings.MQTT(
            host=self.settings.mqtt_host,
            port=self.settings.mqtt_port,
            username=self.settings.mqtt_user if self.settings.mqtt_user else None,
            password=self.settings.mqtt_password.get_secret_value() if self.settings.mqtt_password else None,
        )

    def initialize_components(self) -> None:
        """Initialize application components."""
        # Initialize WebSocket message parser
        self.parser = WebSocketMessageParser()

        # Initialize device manager
        self.device_manager = DeviceManager(
            mqtt_settings=self.mqtt_settings,
            api_client=self.api_client,
        )
        self.device_manager.parser = self.parser

        # Create service coordinator
        self.coordinator = ServiceCoordinator(
            api_client=self.api_client,
            device_manager=self.device_manager,
        )


class ServiceRunner:
    """Runs the main service loop."""

    def __init__(
        self,
        coordinator: ServiceCoordinator,
        resource_manager: ResourceManager,
    ):
        """Initialize the service runner.

        Args:
            coordinator: Service coordinator
            resource_manager: Resource manager
        """
        self.coordinator = coordinator
        self.resource_manager = resource_manager

    async def setup_devices(
        self,
        devices: dict[str, str],
        username: str,
        apikey: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Setup all devices and start WebSocket connections.

        Args:
            devices: Dictionary of device_id -> device_name
            username: Ryobi username
            apikey: Ryobi API key
            session: aiohttp ClientSession
        """
        for device_id, device_name in devices.items():
            # Setup device through coordinator
            try:
                ws = await self.coordinator.setup_device(
                    device_id=device_id,
                    device_name=device_name,
                    username=username,
                    apikey=apikey,
                    session=session,
                )
            except (ValueError, RyobiApiError) as e:
                log.error("Failed to setup device %s: %s", device_id, e)
                continue

            # Start WebSocket listening
            task = asyncio.create_task(ws.listen())
            self.resource_manager.add_task(task)

    async def run(self) -> None:
        """Run the main service loop."""
        try:
            await asyncio.gather(*self.resource_manager._tasks)
        except asyncio.CancelledError:
            log.info("Shutting down WebSocket connections...")
            await self.resource_manager.cleanup()


class RyobiGDO2MQTT:
    """RyobiGDO 2 MQTT service."""

    def __init__(self):
        """Initialize the service."""
        self.resource_manager = ResourceManager()

    async def __aenter__(self):
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager and cleanup resources."""
        await self.resource_manager.cleanup()

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
        # Bootstrap application
        bootstrap = ApplicationBootstrap(settings)
        bootstrap.configure_logging()

        # Initialize session
        async with await bootstrap.initialize_session() as session:
            self.resource_manager.session = session

            # Authenticate
            await bootstrap.authenticate(session)

            # Discover devices
            all_devices = await bootstrap.discover_devices()

            # Initialize MQTT and components
            bootstrap.initialize_mqtt()
            bootstrap.initialize_components()

            # Store coordinator in resource manager
            self.resource_manager.coordinator = bootstrap.coordinator

            # Create service runner
            runner = ServiceRunner(
                coordinator=bootstrap.coordinator,
                resource_manager=self.resource_manager,
            )

            # Setup devices and start WebSocket connections
            await runner.setup_devices(
                devices=all_devices,
                username=settings.email,
                apikey=bootstrap.api_client.api_key,
                session=session,
            )

            # Run main service loop
            await runner.run()


ryobi_gdo2_mqtt = RyobiGDO2MQTT()
