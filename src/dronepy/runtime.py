from __future__ import annotations

from pathlib import Path

from .device_inventory import DeviceInventoryDetector
from .executor import ExecutionEngine
from .fc_probe import FlightControllerProber
from .planner.interfaces import LearnedPlanner, NullPlanner
from .profile_store import ProfileStore
from .safety import SafetyGuard
from .schemas import MissionRequest, PlannerFeatures, RuntimeSnapshot, TelemetrySnapshot


class DroneRuntime:
    def __init__(
        self,
        detector: DeviceInventoryDetector | None = None,
        prober: FlightControllerProber | None = None,
        planner: LearnedPlanner | None = None,
        executor: ExecutionEngine | None = None,
        safety: SafetyGuard | None = None,
        profiles: ProfileStore | None = None,
    ) -> None:
        self.detector = detector or DeviceInventoryDetector()
        self.prober = prober or FlightControllerProber()
        self.planner = planner or NullPlanner()
        self.executor = executor or ExecutionEngine()
        self.safety = safety or SafetyGuard()
        self.profiles = profiles or ProfileStore()

    def inspect(self, telemetry: TelemetrySnapshot | None = None) -> RuntimeSnapshot:
        telemetry = telemetry or TelemetrySnapshot()
        devices = self.detector.detect()
        controller = self.prober.probe(devices)
        profile_path: Path | None = None
        if controller is not None:
            historical = self.profiles.load(controller.controller_id)
            observed_capabilities = [
                item["capability"]
                for item in historical.get("history", [])
                if item.get("status") == "success" and "capability" in item
            ]
            controller = self.prober.merge_observations(controller, observed_capabilities)
            profile_path = self.profiles.save_profile(controller)
        return RuntimeSnapshot(
            devices=devices,
            controller=controller,
            telemetry=telemetry,
            profile_path=profile_path,
        )

    def plan(
        self,
        request: MissionRequest,
        snapshot: RuntimeSnapshot | None = None,
    ):
        snapshot = snapshot or self.inspect()
        prior_outcomes: list[dict[str, object]] = []
        if snapshot.controller is not None:
            prior_outcomes = self.profiles.load(snapshot.controller.controller_id).get("history", [])
        features = PlannerFeatures(
            request=request,
            devices=snapshot.devices,
            controller=snapshot.controller,
            telemetry=snapshot.telemetry,
            prior_outcomes=prior_outcomes,
        )
        return self.planner.plan(features)

    def execute(
        self,
        request: MissionRequest,
        snapshot: RuntimeSnapshot | None = None,
    ):
        snapshot = snapshot or self.inspect()
        plan = self.plan(request, snapshot=snapshot)
        safety = self.safety.evaluate(plan, snapshot.telemetry, snapshot.controller)
        report = self.executor.execute(plan, safety)
        if snapshot.controller is not None:
            for action in report.executed_actions:
                self.profiles.record_outcome(
                    snapshot.controller.controller_id,
                    {"action": action, "capability": action, "status": "success"},
                )
            for action in report.failed_actions:
                self.profiles.record_outcome(
                    snapshot.controller.controller_id,
                    {"action": action, "capability": action, "status": "failed"},
                )
        return report

