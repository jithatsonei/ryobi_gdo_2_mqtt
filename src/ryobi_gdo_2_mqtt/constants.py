"""Constants for Ryobi GDO 2 MQTT integration."""

from enum import IntEnum, StrEnum

HOST_URI = "tti.tiwiconnect.com"
LOGIN_ENDPOINT = "api/login"
DEVICE_GET_ENDPOINT = "api/devices"
DEVICE_SET_ENDPOINT = "api/wsrpc"
REQUEST_TIMEOUT = 3
COORDINATOR = "coordinator"


class DoorStates(IntEnum):
    """Door state values and their string representations."""

    CLOSED = 0
    OPEN = 1
    CLOSING = 2
    OPENING = 3
    FAULT = 4

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


class DoorCommands(IntEnum):
    """Door command values sent to the device."""

    CLOSE = 0
    OPEN = 1
    STOP = 2


class DoorCommandPayloads:
    """Door command payloads from Home Assistant."""

    OPEN = "OPEN"
    CLOSE = "CLOSE"
    STOP = "STOP"


class LightStates(IntEnum):
    """Light state values."""

    OFF = 0
    ON = 1


class LightCommandPayloads:
    """Light command payloads from Home Assistant."""

    ON = "ON"
    OFF = "OFF"


# Battery threshold
BATTERY_LOW_THRESHOLD = 20


class WebSocketState(StrEnum):
    """WebSocket connection states."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    STARTING = "starting"
    STOPPED = "stopped"
