"""Constants for Ryobi GDO 2 MQTT integration."""

from dataclasses import dataclass
from enum import Enum

HOST_URI = "tti.tiwiconnect.com"
LOGIN_ENDPOINT = "api/login"
DEVICE_GET_ENDPOINT = "api/devices"
DEVICE_SET_ENDPOINT = "api/wsrpc"
REQUEST_TIMEOUT = 3
COORDINATOR = "coordinator"


@dataclass(frozen=True)
class DoorStates:
    """Door state values and their string representations."""

    CLOSED: int = 0
    OPEN: int = 1
    CLOSING: int = 2
    OPENING: int = 3
    FAULT: int = 4

    @classmethod
    def to_string(cls, value: int) -> str:
        """Convert door state value to string."""
        mapping = {
            cls.CLOSED: "closed",
            cls.OPEN: "open",
            cls.CLOSING: "closing",
            cls.OPENING: "opening",
            cls.FAULT: "fault",
        }
        return mapping.get(value, "unknown")


@dataclass(frozen=True)
class DoorCommands:
    """Door command values sent to the device."""

    OPEN: int = 1
    CLOSE: int = 0
    STOP: int = 2


@dataclass(frozen=True)
class DoorCommandPayloads:
    """Door command payloads from Home Assistant."""

    OPEN: str = "OPEN"
    CLOSE: str = "CLOSE"
    STOP: str = "STOP"


@dataclass(frozen=True)
class LightStates:
    """Light state values."""

    ON: int = 1
    OFF: int = 0


@dataclass(frozen=True)
class LightCommandPayloads:
    """Light command payloads from Home Assistant."""

    ON: str = "ON"
    OFF: str = "OFF"


# Battery threshold
BATTERY_LOW_THRESHOLD = 20


class WebSocketState(str, Enum):
    """WebSocket connection states."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    STARTING = "starting"
    STOPPED = "stopped"
