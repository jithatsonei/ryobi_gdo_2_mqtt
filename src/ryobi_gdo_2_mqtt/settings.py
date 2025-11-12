from pydantic import Field, SecretStr
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
