"""Configuration loading and validation for DronePy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config_autogen import AutoConfigBuilder


class ConfigError(ValueError):
    """Raised when the runtime configuration is missing required fields."""


class ConfigLoader:
    """Load and validate a DronePy JSON configuration file."""

    REQUIRED_SCHEMA: dict[str, Any] = {
        "hardware": {
            "flight_controller": {
                "type": str,
                "port": str,
                "baud": int,
                "protocol": str,
            },
            "sensors": list,
            "companion_computer": {
                "type": str,
                "ram_gb": int,
            },
        },
        "mission_behavior": {
            "default_altitude_m": int,
            "rtl_on_low_battery": bool,
            "battery_cutoff_voltage": float,
            "max_mission_duration_min": int,
            "log_sensor_data": bool,
            "log_interval_sec": int,
        },
        "planner": {
            "model_path": str,
            "fallback": str,
            "temperature": float,
            "max_tokens": int,
        },
        "logging": {
            "db_path": str,
            "retain_days": int,
        },
    }

    SENSOR_REQUIRED_FIELDS = {
        "name": str,
        "type": str,
    }

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        """Return the validated configuration as a plain dictionary."""
        if not self.path.exists():
            raise ConfigError(f"Config file not found: {self.path}")

        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        self._validate_mapping(data, self.REQUIRED_SCHEMA)
        self._validate_sensors(data["hardware"]["sensors"])
        return data

    def load_or_create(self, detector=None) -> dict[str, Any]:
        """Load config, or generate and persist one when missing."""
        if not self.path.exists():
            builder = AutoConfigBuilder(detector=detector)
            config = builder.generate()
            builder.save(self.path, config)
        return self.load()

    def _validate_mapping(self, data: dict[str, Any], schema: dict[str, Any], prefix: str = "") -> None:
        for field, expected in schema.items():
            qualified_name = f"{prefix}.{field}" if prefix else field
            if field not in data:
                raise ConfigError(f"Missing required field: {qualified_name}")

            value = data[field]
            if isinstance(expected, dict):
                if not isinstance(value, dict):
                    raise ConfigError(
                        f"Wrong type for {qualified_name}: expected object, got {type(value).__name__}"
                    )
                self._validate_mapping(value, expected, prefix=qualified_name)
                continue

            if not isinstance(value, expected):
                # Allow ints where float is expected because JSON numeric literals are often ints.
                if expected is float and isinstance(value, int):
                    continue
                raise ConfigError(
                    f"Wrong type for {qualified_name}: expected {expected.__name__}, got {type(value).__name__}"
                )

    def _validate_sensors(self, sensors: list[dict[str, Any]]) -> None:
        for index, sensor in enumerate(sensors):
            if not isinstance(sensor, dict):
                raise ConfigError(
                    f"Wrong type for hardware.sensors[{index}]: expected object, got {type(sensor).__name__}"
                )
            for field, expected in self.SENSOR_REQUIRED_FIELDS.items():
                if field not in sensor:
                    raise ConfigError(f"Missing required field: hardware.sensors[{index}].{field}")
                if not isinstance(sensor[field], expected):
                    raise ConfigError(
                        f"Wrong type for hardware.sensors[{index}].{field}: "
                        f"expected {expected.__name__}, got {type(sensor[field]).__name__}"
                    )
