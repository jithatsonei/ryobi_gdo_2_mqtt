import json

from aiohttp import ClientSession, ServerConnectionError, ServerTimeoutError

from ryobi_gdo_2_mqtt.constants import DEVICE_GET_ENDPOINT, HOST_URI, LOGIN_ENDPOINT
from ryobi_gdo_2_mqtt.logging import log
from ryobi_gdo_2_mqtt.models import Auth, DeviceData, LoginResponse, LoginResult, MetaData, WskAuthAttempt


class RyobiApiClient:
    """Client for interacting with the Ryobi API."""

    DOOR_STATE = {
        "0": "closed",
        "1": "open",
        "2": "closing",
        "3": "opening",
        "4": "fault",
    }

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
        """Get api_key from Ryobi."""
        auth_ok = False
        url = f"https://{HOST_URI}/{LOGIN_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        method = "post"
        request = await self._process_request(url, method, data)
        if request is None:
            return auth_ok
        try:
            # Parse response into DTO
            wsk_attempts = [WskAuthAttempt(**attempt) for attempt in request["result"]["metaData"]["wskAuthAttempts"]]
            metadata = MetaData(
                userName=request["result"]["metaData"]["userName"],
                authCount=request["result"]["metaData"]["authCount"],
                wskAuthAttempts=wsk_attempts,
            )
            auth = Auth(
                apiKey=request["result"]["auth"]["apiKey"],
                regPin=request["result"]["auth"]["regPin"],
                clientUserName=request["result"]["auth"]["clientUserName"],
                createdDate=request["result"]["auth"]["createdDate"],
                childSelectors=request["result"]["auth"]["childSelectors"],
            )
            result = LoginResult(
                _id=request["result"]["_id"],
                varName=request["result"]["varName"],
                metaData=metadata,
                enabled=request["result"]["enabled"],
                deleted=request["result"]["deleted"],
                createdDate=request["result"]["createdDate"],
                activated=request["result"]["activated"],
                auth=auth,
            )
            login_response = LoginResponse(result=result)
            self.api_key = login_response.api_key
            auth_ok = True
        except KeyError:
            log.error("Exception while parsing Ryobi answer to get API key")
        return auth_ok

    async def _process_request(self, url: str, method: str, data: dict[str, str]) -> dict | None:
        """Process HTTP requests."""
        http_hethod = getattr(self.session, method)
        log.debug("Connecting to %s using %s", url, method)
        reply = None
        try:
            async with http_hethod(url, data=data) as response:
                rawReply = await response.text()
                try:
                    reply = json.loads(rawReply)
                    if not isinstance(reply, dict):
                        reply = None
                except ValueError:
                    log.warning("Reply was not in JSON format: %s", rawReply)

                if response.status in [404, 405, 500]:
                    log.warning("HTTP Error: %s", rawReply)
        except (TimeoutError, ServerTimeoutError):
            log.error("Timeout connecting to %s", url)
        except ServerConnectionError:
            log.error("Problem connecting to server at %s", url)
        return reply

    async def check_device_id(self) -> bool:
        """Check device_id from Ryobi."""
        device_found = False
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        method = "get"
        request = await self._process_request(url, method, data)
        if request is None:
            return device_found
        try:
            result = request["result"]
        except KeyError:
            return device_found
        if len(result) == 0:
            log.error("API error: empty result")
        else:
            for data in result:
                if data["varName"] == self.device_id:
                    device_found = True
        return device_found

    async def get_devices(self) -> dict[str, str]:
        """Return list of devices found."""
        devices = {}
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}"
        data = {"username": self.username, "password": self.password}
        method = "get"
        request = await self._process_request(url, method, data)
        if request is None:
            return devices
        try:
            result = request["result"]
        except KeyError:
            return devices
        if len(result) == 0:
            log.error("API error: empty result")
        else:
            for data in result:
                devices[data["varName"]] = data["metaData"]["name"]
        return devices

    async def update_device(self, device_id: str) -> DeviceData | None:
        """Update device status and parse modules.

        Args:
            device_id: The device ID to update

        Returns:
            DeviceData object containing device data or None on error
        """
        url = f"https://{HOST_URI}/{DEVICE_GET_ENDPOINT}/{device_id}"
        data = {"username": self.username, "password": self.password}
        method = "get"
        request = await self._process_request(url, method, data)

        if request is None:
            return None

        try:
            dtm = request["result"][0]["deviceTypeMap"]

            # Parse the modules for this device
            result = await self._index_modules(device_id, dtm)
            log.debug("Modules indexed for %s: %s", device_id, self._device_modules.get(device_id))

            if not result:
                return None

            device_modules = self._device_modules[device_id]
            device_data_dict = {}

            # Parse initial values
            if "garageDoor" in device_modules:
                door_state = dtm[device_modules["garageDoor"]]["at"]["doorState"]["value"]
                device_data_dict["door_state"] = self.DOOR_STATE[str(door_state)]
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
            return None

    async def _index_modules(self, device_id: str, dtm: dict) -> bool:
        """Index and add modules to dictionary for a specific device.

        Args:
            device_id: The device ID
            dtm: Device type map from API response

        Returns:
            True if successful, False otherwise
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
            return False

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
        """
        module_type = {
            "garageDoor": 5,
            "backupCharger": 6,
            "garageLight": 5,
            "wifiModule": 7,
            "parkAssistLaser": 1,
            "inflator": 4,
            "btSpeaker": 2,
            "fan": 3,
        }
        return module_type.get(module)
