"""Capability profile built from config-declared sensors and live FC state."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .schemas import FCCapabilities


@dataclass(slots=True)
class CapabilityProfile:
    """Single source of truth for hardware and flight-controller capabilities."""

    sensors: list[dict[str, Any]]
    fc: FCCapabilities
    metadata: dict[str, Any] = field(default_factory=dict)
    _sensor_map: dict[str, dict[str, Any]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._sensor_map = {sensor["name"]: deepcopy(sensor) for sensor in self.sensors}
        if "gps" in self._sensor_map:
            self._sensor_map["gps"]["available"] = self.fc.has_gps
            self._sensor_map["gps"]["fix_type"] = self.fc.gps_fix_type
        for name, sensor in self._sensor_map.items():
            sensor.setdefault("available", True)
            if name == "fc":
                sensor["available"] = self.fc.reachable

    @classmethod
    def from_config(cls, config: dict[str, Any], fc: FCCapabilities) -> "CapabilityProfile":
        """Build a profile using the declared sensor list from config."""
        sensors = deepcopy(config["hardware"]["sensors"])
        return cls(sensors=sensors, fc=fc, metadata={"companion_computer": config["hardware"]["companion_computer"]})

    def has(self, name: str) -> bool:
        """Return whether a sensor or synthetic capability is available."""
        if name == "fc":
            return self.fc.reachable
        sensor = self._sensor_map.get(name)
        return bool(sensor and sensor.get("available", True))

    def get(self, name: str) -> dict[str, Any] | None:
        """Return a copy of the sensor entry if present."""
        sensor = self._sensor_map.get(name)
        return deepcopy(sensor) if sensor else None

    def all_sensors(self) -> list[dict[str, Any]]:
        """Return all declared sensors with availability annotations."""
        return [deepcopy(sensor) for sensor in self._sensor_map.values()]
