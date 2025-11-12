"""Tests for settings."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ryobi_gdo_2_mqtt.settings import Settings


class TestSettings:
    """Tests for Settings."""

    def test_settings_with_all_fields(self):
        """Test creating settings with all fields."""
        # Disable CLI parsing during tests
        with patch.dict(os.environ, {}, clear=False):
            settings = Settings(
                email="test@example.com",
                password="testpass",
                mqtt_host="localhost",
                mqtt_port=1883,
                mqtt_user="mqttuser",
                mqtt_password="mqttpass",
                log_level="DEBUG",
                _cli_parse_args=False,
            )

        assert settings.email == "test@example.com"
        assert settings.password.get_secret_value() == "testpass"
        assert settings.mqtt_host == "localhost"
        assert settings.mqtt_port == 1883
        assert settings.mqtt_user == "mqttuser"
        assert settings.mqtt_password.get_secret_value() == "mqttpass"
        assert settings.log_level == "DEBUG"

    def test_settings_with_defaults(self):
        """Test creating settings with default values."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.argv", ["test"]):
                settings = Settings(email="test@example.com", password="testpass", mqtt_host="localhost")

        assert settings.mqtt_port == 1883
        assert settings.mqtt_user == ""
        assert settings.mqtt_password.get_secret_value() == ""

    def test_settings_password_is_secret(self):
        """Test that password is stored as SecretStr."""
        with patch.dict(os.environ, {}, clear=False):
            settings = Settings(
                email="test@example.com", password="testpass", mqtt_host="localhost", _cli_parse_args=False
            )

        # Password should not be visible in repr
        assert "testpass" not in str(settings)
        assert "testpass" not in repr(settings)

        # But can be accessed via get_secret_value()
        assert settings.password.get_secret_value() == "testpass"

    def test_mqtt_port_validation_valid(self):
        """Test that valid MQTT ports are accepted."""
        with patch.dict(os.environ, {}, clear=False):
            # Test minimum valid port
            settings = Settings(
                email="test@example.com", password="testpass", mqtt_host="localhost", mqtt_port=1, _cli_parse_args=False
            )
            assert settings.mqtt_port == 1

            # Test maximum valid port
            settings = Settings(
                email="test@example.com",
                password="testpass",
                mqtt_host="localhost",
                mqtt_port=65535,
                _cli_parse_args=False,
            )
            assert settings.mqtt_port == 65535

            # Test common MQTT port
            settings = Settings(
                email="test@example.com",
                password="testpass",
                mqtt_host="localhost",
                mqtt_port=1883,
                _cli_parse_args=False,
            )
            assert settings.mqtt_port == 1883

    def test_mqtt_port_validation_invalid(self):
        """Test that invalid MQTT ports are rejected."""
        with patch.dict(os.environ, {}, clear=False):
            # Test port too low
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    email="test@example.com",
                    password="testpass",
                    mqtt_host="localhost",
                    mqtt_port=0,
                    _cli_parse_args=False,
                )
            assert "Port must be between 1 and 65535" in str(exc_info.value)

            # Test port too high
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    email="test@example.com",
                    password="testpass",
                    mqtt_host="localhost",
                    mqtt_port=65536,
                    _cli_parse_args=False,
                )
            assert "Port must be between 1 and 65535" in str(exc_info.value)

            # Test negative port
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    email="test@example.com",
                    password="testpass",
                    mqtt_host="localhost",
                    mqtt_port=-1,
                    _cli_parse_args=False,
                )
            assert "Port must be between 1 and 65535" in str(exc_info.value)

    def test_log_level_validation_valid(self):
        """Test that valid log levels are accepted and normalized."""
        with patch.dict(os.environ, {}, clear=False):
            # Test all valid log levels
            for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                settings = Settings(
                    email="test@example.com",
                    password="testpass",
                    mqtt_host="localhost",
                    log_level=level,
                    _cli_parse_args=False,
                )
                assert settings.log_level == level

            # Test lowercase is normalized to uppercase
            settings = Settings(
                email="test@example.com",
                password="testpass",
                mqtt_host="localhost",
                log_level="debug",
                _cli_parse_args=False,
            )
            assert settings.log_level == "DEBUG"

            # Test mixed case is normalized to uppercase
            settings = Settings(
                email="test@example.com",
                password="testpass",
                mqtt_host="localhost",
                log_level="WaRnInG",
                _cli_parse_args=False,
            )
            assert settings.log_level == "WARNING"

    def test_log_level_validation_invalid(self):
        """Test that invalid log levels are rejected."""
        with patch.dict(os.environ, {}, clear=False):
            # Test invalid log level
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    email="test@example.com",
                    password="testpass",
                    mqtt_host="localhost",
                    log_level="INVALID",
                    _cli_parse_args=False,
                )
            assert "Log level must be one of" in str(exc_info.value)

            # Test empty log level
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    email="test@example.com",
                    password="testpass",
                    mqtt_host="localhost",
                    log_level="",
                    _cli_parse_args=False,
                )
            assert "Log level must be one of" in str(exc_info.value)
