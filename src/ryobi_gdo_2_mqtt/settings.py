from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for Ryobi GDO 2 MQTT integration."""

    model_config = SettingsConfigDict(
        env_prefix="RYOBI_",
        env_file=".env",
        env_file_encoding="utf-8",
        cli_parse_args=True,
        cli_avoid_json=True,
        case_sensitive=False,
        extra="ignore",
    )

    email: str = Field(description="Ryobi account email address")
    password: SecretStr = Field(description="Ryobi account password")
    mqtt_host: str = Field(description="MQTT broker hostname or IP address")
    mqtt_port: int = Field(default=1883, description="MQTT broker port")
    mqtt_user: str = Field(default="", description="MQTT broker username")
    mqtt_password: SecretStr = Field(default="", description="MQTT broker password")
    log_level: str = Field(default="INFO", description="Logging level")

    @field_validator("mqtt_port")
    @classmethod
    def validate_port(cls, v):
        """Validate MQTT port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is a valid logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
