from __future__ import annotations

from ..schemas import FlightControllerProfile, MissionPlan, SafetyDecision, TelemetrySnapshot


class SafetyGuard:
    def __init__(
        self,
        min_battery_percent: float = 15.0,
        min_link_quality: float = 0.2,
    ) -> None:
        self.min_battery_percent = min_battery_percent
        self.min_link_quality = min_link_quality

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

