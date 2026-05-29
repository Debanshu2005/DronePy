from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DetectedDevice:
    device_id: str
    category: str
    transport: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CapabilityEvidence:
    capability: str
    source: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FlightControllerProfile:
    controller_id: str
    family: str
    transport: str
    firmware_version: str | None = None
    capabilities: list[str] = field(default_factory=list)
    modes: list[str] = field(default_factory=list)
    telemetry_topics: list[str] = field(default_factory=list)
    limits: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    evidence: list[CapabilityEvidence] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MissionRequest:
    text: str
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TelemetrySnapshot:
    battery_percent: float | None = None
    link_quality: float | None = None
    gps_fix: bool | None = None
    armed: bool | None = None
    flight_mode: str | None = None
    position: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PlannerFeatures:
    request: MissionRequest
    devices: list[DetectedDevice]
    controller: FlightControllerProfile | None
    telemetry: TelemetrySnapshot
    prior_outcomes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MissionPlan:
    plan_id: str
    intent: str
    actions: list[str]
    required_capabilities: list[str] = field(default_factory=list)
    missing_capabilities: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(slots=True)
class SafetyDecision:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionReport:
    plan: MissionPlan
    safety: SafetyDecision
    executed_actions: list[str] = field(default_factory=list)
    failed_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(slots=True)
class RuntimeSnapshot:
    devices: list[DetectedDevice]
    controller: FlightControllerProfile | None
    telemetry: TelemetrySnapshot
    profile_path: Path | None = None

    def to_json(self) -> str:
        payload = asdict(self)
        payload["profile_path"] = str(self.profile_path) if self.profile_path else None
        return json.dumps(payload, indent=2, sort_keys=True)

