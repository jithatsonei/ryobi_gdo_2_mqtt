import json

from aiohttp import ClientSession, ServerConnectionError, ServerTimeoutError

from ryobi_gdo_2_mqtt.constants import DEVICE_GET_ENDPOINT, HOST_URI, LOGIN_ENDPOINT, DoorStates
from ryobi_gdo_2_mqtt.exceptions import (
    RyobiAuthenticationError,
    RyobiConnectionError,
    RyobiDeviceNotFoundError,
    RyobiInvalidResponseError,
)
from ryobi_gdo_2_mqtt.logging import log
from ryobi_gdo_2_mqtt.models import Auth, DeviceData, LoginResponse, LoginResult, MetaData, WskAuthAttempt


class RyobiApiClient:
    """Client for interacting with the Ryobi API."""

    def __init__(self, username: str, password: str, session: ClientSession):
        """Initialize the Ryobi API client.

        Args:
            username: Ryobi account username/email
            password: Ryobi account password
            session: aiohttp ClientSession for making requests
        """
        self.username = username
        self.password = password
        self.session = session
        self.api_key = None
        self._device_modules: dict[str, dict[str, str]] = {}

    async def get_api_key(self) -> bool:
        """Get api_key from Ryobi.

        Returns:
            True if authentication successful

        Raises:
            RyobiAuthenticationError: If authentication fails
            RyobiInvalidResponseError: If response format is invalid
        """
        url = f"https://{HOST_URI}/{LOGIN_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        method = "post"
        request = await self._process_request(url, method, data)
        if request is None:
            raise RyobiAuthenticationError("Failed to get response from login endpoint")
        try:
            result_block = request.get("result")
            if not isinstance(result_block, dict):
                raise RyobiInvalidResponseError("Invalid login response: missing result object")

            auth_block = result_block.get("auth") or {}
            api_key = auth_block.get("apiKey")
            if not api_key:
                raise RyobiInvalidResponseError("Invalid login response: apiKey missing")

            meta_block = result_block.get("metaData") or {}
            username_from_response = (
                meta_block.get("userName")
                or result_block.get("varName")
                or self.username
            )
            wsk_attempts: list[WskAuthAttempt] = []
            for attempt in meta_block.get("wskAuthAttempts") or []:
                if not isinstance(attempt, dict):
                    continue
                try:
                    wsk_attempts.append(WskAuthAttempt(**attempt))
                except Exception as exc:
                    log.debug("Skipping malformed auth attempt entry %s: %s", attempt, exc)

            metadata = MetaData(
                userName=username_from_response,
                authCount=meta_block.get("authCount"),
                wskAuthAttempts=wsk_attempts,
            )

            auth = Auth(
                apiKey=api_key,
                regPin=auth_block.get("regPin"),
                clientUserName=auth_block.get("clientUserName"),
                createdDate=auth_block.get("createdDate"),
                childSelectors=auth_block.get("childSelectors") or [],
            )
            login_response = LoginResponse(
                result=LoginResult(
                    _id=result_block.get("_id"),
                    varName=result_block.get("varName"),
                    metaData=metadata,
                    enabled=result_block.get("enabled"),
                    deleted=result_block.get("deleted"),
                    createdDate=result_block.get("createdDate"),
                    activated=result_block.get("activated"),
                    auth=auth,
                )
            )
            self.api_key = login_response.api_key
            return True
        except RyobiInvalidResponseError:
            raise
        except Exception as e:
            log.error("Exception while parsing Ryobi answer to get API key: %s", e)
            raise RyobiInvalidResponseError(f"Invalid login response format: {e}") from e

    async def _process_request(self, url: str, method: str, data: dict[str, str]) -> dict | None:
        """Process HTTP requests.

        Raises:
            RyobiConnectionError: If connection fails or times out
            RyobiInvalidResponseError: If response is not valid JSON or has error status
        """
        http_hethod = getattr(self.session, method)
        log.debug("Connecting to %s using %s", url, method)
        try:
            async with http_hethod(url, data=data) as response:
                rawReply = await response.text()
                try:
                    reply = json.loads(rawReply)
                    if not isinstance(reply, dict):
                        raise RyobiInvalidResponseError(f"Response is not a dictionary: {rawReply}")
                except ValueError as e:
                    log.warning("Reply was not in JSON format: %s", rawReply)
                    raise RyobiInvalidResponseError(f"Invalid JSON response: {rawReply}") from e

                if response.status in [404, 405, 500]:
                    log.warning("HTTP Error: %s", rawReply)
                    raise RyobiInvalidResponseError(f"HTTP error {response.status}: {rawReply}")

                return reply
        except (TimeoutError, ServerTimeoutError) as e:
            log.error("Timeout connecting to %s", url)
            raise RyobiConnectionError(f"Timeout connecting to {url}") from e
        except ServerConnectionError as e:
            log.error("Problem connecting to server at %s", url)
            raise RyobiConnectionError(f"Connection error to {url}") from e

    async def check_device_id(self) -> bool:
        """Check device_id from Ryobi.

        Raises:
            RyobiInvalidResponseError: If response format is invalid
        """
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        method = "get"
        request = await self._process_request(url, method, data)
        try:
            result = request["result"]
        except KeyError as e:
            raise RyobiInvalidResponseError("Invalid device list response format") from e
        if len(result) == 0:
            log.error("API error: empty result")
            return False
        else:
            for data in result:
                if data["varName"] == self.device_id:
                    return True
        return False

    async def get_devices(self) -> dict[str, str]:
        """Return list of devices found.

        Raises:
            RyobiInvalidResponseError: If response format is invalid
            RyobiDeviceNotFoundError: If no devices found
        """
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        method = "get"
        request = await self._process_request(url, method, data)
        try:
            result = request["result"]
        except KeyError as e:
            raise RyobiInvalidResponseError("Invalid device list response format") from e
        if len(result) == 0:
            log.error("API error: empty result")
            raise RyobiDeviceNotFoundError("No devices found in account")

        devices = {}
        for data in result:
            devices[data["varName"]] = data["metaData"]["name"]
        return devices

    async def update_device(self, device_id: str) -> DeviceData | None:
        """Update device status and parse modules.

        Args:
            device_id: The device ID to update

        Returns:
            DeviceData object containing device data

        Raises:
            RyobiInvalidResponseError: If response format is invalid
        """
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}/{device_id}"
        data = {"username": self.username, "password": self.password}
        method = "get"
        request = await self._process_request(url, method, data)

        try:
            dtm = request["result"][0]["deviceTypeMap"]

            # Parse the modules for this device
            result = await self._index_modules(device_id, dtm)
            log.debug("Modules indexed for %s: %s", device_id, self._device_modules.get(device_id))

            if not result:
                raise RyobiInvalidResponseError(f"Failed to index modules for device {device_id}")

            device_modules = self._device_modules[device_id]
            device_data_dict = {}

            # Parse initial values
            if "garageDoor" in device_modules:
                door_state = dtm[device_modules["garageDoor"]]["at"]["doorState"]["value"]
                device_data_dict["door_state"] = DoorStates.to_string(door_state)
                device_data_dict["safety"] = dtm[device_modules["garageDoor"]]["at"]["sensorFlag"]["value"]
                device_data_dict["vacation_mode"] = dtm[device_modules["garageDoor"]]["at"]["vacationMode"]["value"]

                if "motionSensor" in dtm[device_modules["garageDoor"]]["at"]:
                    device_data_dict["motion"] = dtm[device_modules["garageDoor"]]["at"]["motionSensor"]["value"]

            if "garageLight" in device_modules:
                device_data_dict["light_state"] = dtm[device_modules["garageLight"]]["at"]["lightState"]["value"]

            if "backupCharger" in device_modules:
                device_data_dict["battery_level"] = dtm[device_modules["backupCharger"]]["at"]["chargeLevel"]["value"]

            if "wifiModule" in device_modules:
                device_data_dict["wifi_rssi"] = dtm[device_modules["wifiModule"]]["at"]["rssi"]["value"]

            if "parkAssistLaser" in device_modules:
                device_data_dict["park_assist"] = dtm[device_modules["parkAssistLaser"]]["at"]["moduleState"]["value"]

            if "inflator" in device_modules:
                device_data_dict["inflator"] = dtm[device_modules["inflator"]]["at"]["moduleState"]["value"]

            if "btSpeaker" in device_modules:
                device_data_dict["bt_speaker"] = dtm[device_modules["btSpeaker"]]["at"]["moduleState"]["value"]
                device_data_dict["mic_status"] = dtm[device_modules["btSpeaker"]]["at"]["micEnable"]["value"]

            if "fan" in device_modules:
                device_data_dict["fan"] = dtm[device_modules["fan"]]["at"]["speed"]["value"]

            if "name" in request["result"][0]["metaData"]:
                device_data_dict["device_name"] = request["result"][0]["metaData"]["name"]

            device_data = DeviceData(**device_data_dict)
            log.debug("Device data: %s", device_data)

            return device_data

        except KeyError as error:
            log.error("Exception while parsing device update: %s", error)
            raise RyobiInvalidResponseError(f"Invalid device data format for {device_id}: {error}") from error

    async def _index_modules(self, device_id: str, dtm: dict) -> bool:
        """Index and add modules to dictionary for a specific device.

        Args:
            device_id: The device ID
            dtm: Device type map from API response

        Returns:
            True if successful

        Raises:
            RyobiInvalidResponseError: If module parsing fails
        """
        # Known modules
        module_list = [
            "garageDoor",
            "backupCharger",
            "garageLight",
            "wifiModule",
            "parkAssistLaser",
            "inflator",
            "btSpeaker",
            "fan",
        ]

        frame = {}
        try:
            for key in dtm:
                for module in module_list:
                    if module in key:
                        frame[module] = key
        except Exception as err:
            log.error("Problem parsing module list: %s", err)
            raise RyobiInvalidResponseError(f"Failed to parse module list for {device_id}: {err}") from err

        self._device_modules[device_id] = frame
        return True

    def get_module(self, device_id: str, module: str) -> int | None:
        """Return module number for device.

        Args:
            device_id: The device ID
            module: Module name (e.g., "garageDoor", "garageLight")

        Returns:
            Module port ID or None if not found
        """
        device_modules = self._device_modules.get(device_id)
        if device_modules is None or module not in device_modules:
            return None
        return int(device_modules[module].split("_")[1])

    def get_module_type(self, module: str) -> int | None:
        """Return module type for device.

        Args:
            module: Module name

        Returns:
            Module type ID or None if not found

        Note:
            This method is deprecated. Module types are now defined in MODULES configuration.
            Kept for backward compatibility.
        """
        from ryobi_gdo_2_mqtt.device_manager import MODULES

        if module in MODULES:
            return MODULES[module].module_type
        return None
