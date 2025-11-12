"""Custom exceptions for Ryobi GDO 2 MQTT integration."""


class RyobiApiError(Exception):
    """Base exception for Ryobi API errors."""

    pass


class RyobiAuthenticationError(RyobiApiError):
    """Authentication failed."""

    pass


class RyobiConnectionError(RyobiApiError):
    """Connection to API failed."""

    pass


class RyobiDeviceNotFoundError(RyobiApiError):
    """Device not found."""

    pass


class RyobiInvalidResponseError(RyobiApiError):
    """Invalid response from API."""

    pass
