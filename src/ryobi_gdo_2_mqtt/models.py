"""Data Transfer Objects for Ryobi GDO 2 MQTT integration."""

from pydantic import BaseModel, Field


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

    userName: str | None = None
    authCount: int | None = None
    wskAuthAttempts: list[WskAuthAttempt] = Field(default_factory=list)


class Auth(BaseModel):
    """Authentication details."""

    apiKey: str
    regPin: str | None = None
    clientUserName: str | None = None
    createdDate: str | None = None
    childSelectors: list[str] = Field(default_factory=list)


class LoginResult(BaseModel):
    """Login result data."""

    _id: str | None = None
    varName: str | None = None
    metaData: MetaData = Field(default_factory=MetaData)
    enabled: bool | None = None
    deleted: bool | None = None
    createdDate: str | None = None
    activated: bool | None = None
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
