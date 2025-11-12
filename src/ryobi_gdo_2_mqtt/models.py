"""Data Transfer Objects for Ryobi GDO 2 MQTT integration."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Login request payload."""

    username: str
    password: str


class WskAuthAttempt(BaseModel):
    """WebSocket authentication attempt."""

    varName: str
    apiKey: str
    ts: str
    success: bool


class MetaData(BaseModel):
    """User metadata from login response."""

    userName: str
    authCount: int
    wskAuthAttempts: list[WskAuthAttempt]


class Auth(BaseModel):
    """Authentication details."""

    apiKey: str
    regPin: str
    clientUserName: str
    createdDate: str
    childSelectors: list[str]


class LoginResult(BaseModel):
    """Login result data."""

    _id: str
    varName: str
    metaData: MetaData
    enabled: bool
    deleted: bool
    createdDate: str
    activated: bool
    auth: Auth


class LoginResponse(BaseModel):
    """Login response data."""

    result: LoginResult

    @property
    def api_key(self) -> str:
        """Get the API key from the response."""
        return self.result.auth.apiKey


class DeviceState(BaseModel):
    """Device state information."""

    device_id: str
    door_state: str
    light_state: str
    battery_level: int | None = None


class DeviceCommand(BaseModel):
    """Command to send to a device."""

    device_id: str
    command: str
    value: str | int | bool


class DeviceData(BaseModel):
    """Structured device data from API."""

    door_state: str | None = None
    light_state: bool | None = None
    battery_level: int | None = None
    safety: int | None = None
    vacation_mode: int | None = None
    motion: int | None = None
    wifi_rssi: int | None = None
    park_assist: int | None = None
    inflator: int | None = None
    bt_speaker: int | None = None
    mic_status: int | None = None
    fan: int | None = None
    device_name: str | None = None
