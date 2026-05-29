from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..capability_profile import CapabilityProfile
from ..schemas import FCCapabilities, FlightControllerProfile, MissionPlan, SafetyDecision, TelemetrySnapshot


@dataclass(slots=True)
class SafetyReport:
    """Safety evaluation result for a structured mission procedure."""

    passed: bool
    blocked_steps: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    action: str = "proceed"


class SafetyGuard:
    def __init__(
        self,
        min_battery_percent: float = 15.0,
        min_link_quality: float = 0.2,
        mission_behavior: dict[str, Any] | None = None,
    ) -> None:
        self.min_battery_percent = min_battery_percent
        self.min_link_quality = min_link_quality
        self.mission_behavior = mission_behavior or {}

    def check(
        self,
        steps: list[dict[str, Any]],
        profile: CapabilityProfile,
        mission_behavior: dict[str, Any] | None = None,
    ) -> SafetyReport:
        """Evaluate a procedure against available hardware and current FC state."""
        behavior = mission_behavior or self.mission_behavior
        warnings: list[str] = []
        blocked_steps: list[int] = []

        if profile.fc.battery_voltage is not None:
            cutoff = float(behavior.get("battery_cutoff_voltage", 0.0))
            if cutoff and profile.fc.battery_voltage < cutoff:
                return SafetyReport(
                    passed=False,
                    blocked_steps=list(range(len(steps))),
                    warnings=["battery below cutoff voltage; initiating RTL"],
                    action="rtl",
                )

        if not profile.fc.reachable:
            return SafetyReport(
                passed=False,
                blocked_steps=list(range(len(steps))),
                warnings=["flight controller not reachable"],
                action="abort",
            )

        flight_actions = {"fly_pattern", "rtl"}
        gps_actions = {"fly_pattern", "geotag", "if_detection"}

        for index, step in enumerate(steps):
            device = step.get("device", "")
            action = step.get("action", "")
            if device and device != "fc" and not profile.has(device):
                blocked_steps.append(index)
                warnings.append(f"step {index} references unavailable device '{device}'")
                continue
            if device == "fc" and not profile.fc.reachable:
                blocked_steps.append(index)
                warnings.append(f"step {index} requires reachable flight controller")
                continue
            if action in gps_actions and profile.fc.gps_fix_type < 3:
                blocked_steps.append(index)
                warnings.append(f"step {index} requires stronger GPS fix")
                continue
            if action in flight_actions and not profile.fc.armed:
                warnings.append(f"step {index} requires the flight controller to be armed first")

        if blocked_steps and warnings:
            return SafetyReport(
                passed=False,
                blocked_steps=blocked_steps,
                warnings=warnings,
                action="proceed_with_warnings",
            )
        if warnings:
            return SafetyReport(
                passed=False,
                blocked_steps=[],
                warnings=warnings,
                action="proceed_with_warnings",
            )
        return SafetyReport(passed=True, blocked_steps=[], warnings=[], action="proceed")

    def evaluate(
        self,
        plan: MissionPlan,
        telemetry: TelemetrySnapshot,
        controller: FlightControllerProfile | None,
    ) -> SafetyDecision:
        reasons: list[str] = []
        capabilities = set(controller.capabilities if controller else [])

        if telemetry.battery_percent is not None and telemetry.battery_percent < self.min_battery_percent:
            reasons.append("battery below safety threshold")
        if telemetry.link_quality is not None and telemetry.link_quality < self.min_link_quality:
            reasons.append("link quality below safety threshold")

        missing = [capability for capability in plan.required_capabilities if capability not in capabilities]
        if missing:
            reasons.append(f"missing controller capabilities: {', '.join(sorted(missing))}")

        if plan.missing_capabilities:
            reasons.append(f"planner reported missing capabilities: {', '.join(sorted(plan.missing_capabilities))}")

        return SafetyDecision(approved=not reasons, reasons=reasons)

    @staticmethod
    def fc_from_legacy_profile(controller: FlightControllerProfile | None) -> FCCapabilities:
        """Bridge legacy controller profiles into the config-driven FC capability model."""
        if controller is None:
            return FCCapabilities.degraded()
        capability_set = set(controller.capabilities)
        return FCCapabilities(
            controller_family=controller.family,
            firmware_version=controller.firmware_version,
            has_gps="telemetry_gps" in capability_set or "telemetry" in capability_set,
            gps_fix_type=3 if "telemetry_gps" in capability_set or "telemetry" in capability_set else 0,
            has_barometer="telemetry" in capability_set,
            has_compass="telemetry" in capability_set,
            battery_voltage=None,
            armed=False,
            reachable=True,
            protocol=controller.transport,
            metadata=controller.metadata,
        )
