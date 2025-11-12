"""Utility functions for Ryobi GDO 2 MQTT integration."""

import json
from pathlib import Path
from typing import Any


def record_json_fixture(data: Any, filename: str) -> None:
    """Record JSON data to a fixture file in tests/fixtures directory.

    Args:
        data: The data to record (will be JSON serialized)
        filename: Name of the fixture file (e.g., "my_fixture.json")
    """
    # Get the project root (assuming utils.py is in src/ryobi_gdo_2_mqtt/)
    project_root = Path(__file__).parent.parent.parent
    fixtures_dir = project_root / "src" / "tests" / "fixtures"

    # Ensure the fixtures directory exists
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # Write the JSON data
    fixture_path = fixtures_dir / filename
    with open(fixture_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Add trailing newline
