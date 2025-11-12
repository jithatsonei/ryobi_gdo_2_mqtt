"""WebSocket message parser for Ryobi API."""

from typing import Any

from ryobi_gdo_2_mqtt.constants import DoorStates
from ryobi_gdo_2_mqtt.logging import log


class WebSocketMessageParser:
    """Parses WebSocket messages from Ryobi API."""

    def __init__(self):
        """Initialize the parser."""
        pass

    def parse_attribute_update(self, data: dict) -> dict[str, Any]:
        """Parse wskAttributeUpdateNtfy messages.

        Args:
            data: WebSocket message data

        Returns:
            Dictionary with parsed updates: {
                'door_state': str,
                'light_state': bool,
                'battery_level': int,
                'motion': int,
                'vacation_mode': int,
                'safety': int,
                'park_assist': int,
                'bt_speaker': int,
                'inflator': int,
                'fan': int,
            }
        """
        updates = {}

        try:
            if data.get("method") != "wskAttributeUpdateNtfy":
                return updates

            params = data.get("params", {})

            for key in params:
                if key in ["topic", "varName", "id"]:
                    continue

                log.debug("Websocket parsing update for item %s: %s", key, params[key])

                # Extract module name from key (e.g., "garageDoor_1.doorState")
                if "." in key:
                    module_name = key.split(".")[1]
                else:
                    module_name = key

                value = params[key].get("value") if isinstance(params[key], dict) else params[key]

                # Garage Door updates
                if "garageDoor" in key:
                    if module_name == "doorState":
                        door_state = DoorStates.to_string(value)
                        if door_state != "unknown":
                            updates["door_state"] = door_state
                    elif module_name == "motionSensor":
                        updates["motion"] = value
                        log.debug("Motion sensor: %s", value)
                    elif module_name == "vacationMode":
                        updates["vacation_mode"] = value
                        log.debug("Vacation mode: %s", value)
                    elif module_name == "sensorFlag":
                        updates["safety"] = value
                        log.debug("Safety sensor: %s", value)

                # Garage Light updates
                elif "garageLight" in key:
                    if module_name == "lightState":
                        updates["light_state"] = bool(value)

                # Battery updates
                elif "backupCharger" in key:
                    if module_name == "chargeLevel":
                        updates["battery_level"] = int(value)

                # Other modules
                elif "parkAssistLaser" in key:
                    updates["park_assist"] = value
                    log.debug("Park assist: %s", value)
                elif "btSpeaker" in key:
                    updates["bt_speaker"] = value
                    log.debug("Bluetooth speaker: %s", value)
                elif "inflator" in key:
                    updates["inflator"] = value
                    log.debug("Inflator: %s", value)
                elif "fan" in key:
                    updates["fan"] = value
                    log.debug("Fan: %s", value)
                else:
                    log.debug("Unhandled module update: %s = %s", key, value)

        except Exception as ex:
            log.error("Error parsing WebSocket message: %s", ex)
            log.exception(ex)

        return updates
