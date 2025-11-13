"""Tests for WebSocket message parser."""

import pytest

from ryobi_gdo_2_mqtt.websocket_parser import WebSocketMessageParser
from tests.conftest import load_fixture


@pytest.fixture
def parser():
    """Create a parser instance."""
    return WebSocketMessageParser()


class TestWebSocketMessageParser:
    """Tests for WebSocketMessageParser."""

    def test_parse_light_state_on(self, parser, fixtures_dir):
        """Test parsing light state change to ON."""
        data = load_fixture(fixtures_dir, "ws_message_1762952732.json")

        updates = parser.parse_attribute_update(data)

        assert "light_state" in updates
        assert updates["light_state"] is True

    def test_parse_light_state_off(self, parser, fixtures_dir):
        """Test parsing light state change to OFF."""
        data = load_fixture(fixtures_dir, "ws_message_1762952736.json")

        updates = parser.parse_attribute_update(data)

        assert "light_state" in updates
        assert updates["light_state"] is False

    def test_parse_door_state_open(self, parser, fixtures_dir):
        """Test parsing door state change to OPEN."""
        data = load_fixture(fixtures_dir, "ws_message_1762952771.json")

        updates = parser.parse_attribute_update(data)

        assert "door_state" in updates
        assert updates["door_state"] == "open"

    def test_parse_door_state_closed(self, parser, fixtures_dir):
        """Test parsing door state change to CLOSED."""
        data = load_fixture(fixtures_dir, "ws_message_1762952798.json")

        updates = parser.parse_attribute_update(data)

        assert "door_state" in updates
        assert updates["door_state"] == "closed"

    def test_parse_door_position_only(self, parser, fixtures_dir):
        """Test parsing door position update without state change."""
        data = load_fixture(fixtures_dir, "ws_message_1762952767.json")

        updates = parser.parse_attribute_update(data)

        # Should not include door_state, only position updates
        assert "door_state" not in updates

    def test_parse_non_attribute_update_message(self, parser, fixtures_dir):
        """Test that non-attribute-update messages return empty dict."""
        data = load_fixture(fixtures_dir, "ws_message_1762952686.json")

        updates = parser.parse_attribute_update(data)

        assert updates == {}

    def test_parse_multiple_attributes(self, parser, fixtures_dir):
        """Test parsing message with multiple attribute updates."""
        data = load_fixture(fixtures_dir, "ws_message_1762952771.json")

        updates = parser.parse_attribute_update(data)

        # This message has both doorState and doorPosition
        assert "door_state" in updates
        assert updates["door_state"] == "open"


class TestWebSocketParserNewEntities:
    """Tests for WebSocket parser with newly added entities."""

    def test_parse_vacation_mode_update(self, parser):
        """Test parsing vacation mode update."""
        data = {
            "method": "wskAttributeUpdateNtfy",
            "params": {
                "garageDoor_7.vacationMode": {"value": 1},
            },
        }

        updates = parser.parse_attribute_update(data)

        assert "vacation_mode" in updates
        assert updates["vacation_mode"] == 1

    def test_parse_park_assist_update(self, parser):
        """Test parsing park assist update."""
        data = {
            "method": "wskAttributeUpdateNtfy",
            "params": {
                "parkAssistLaser_1.moduleState": {"value": 1},
            },
        }

        updates = parser.parse_attribute_update(data)

        assert "park_assist" in updates
        assert updates["park_assist"] == 1

    def test_parse_fan_speed_update(self, parser):
        """Test parsing fan speed update."""
        data = {
            "method": "wskAttributeUpdateNtfy",
            "params": {
                "fan_3.speed": {"value": 75},
            },
        }

        updates = parser.parse_attribute_update(data)

        assert "fan" in updates
        assert updates["fan"] == 75

    def test_parse_inflator_update(self, parser):
        """Test parsing inflator update."""
        data = {
            "method": "wskAttributeUpdateNtfy",
            "params": {
                "inflator_4.moduleState": {"value": 1},
            },
        }

        updates = parser.parse_attribute_update(data)

        assert "inflator" in updates
        assert updates["inflator"] == 1

    def test_parse_bt_speaker_update(self, parser):
        """Test parsing bluetooth speaker update."""
        data = {
            "method": "wskAttributeUpdateNtfy",
            "params": {
                "btSpeaker_2.moduleState": {"value": 1},
            },
        }

        updates = parser.parse_attribute_update(data)

        assert "bt_speaker" in updates
        assert updates["bt_speaker"] == 1
