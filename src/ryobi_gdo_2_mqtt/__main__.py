import sys

from ryobi_gdo_2_mqtt.ryobigdo2mqtt import ryobi_gdo2_mqtt
from ryobi_gdo_2_mqtt.settings import Settings


def main():
    """Entry point of the application."""
    settings = Settings()

    sys.exit(ryobi_gdo2_mqtt(settings=settings))


if __name__ == "__main__":
    main()
