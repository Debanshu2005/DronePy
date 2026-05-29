from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .capability_profile import CapabilityProfile
from .config_loader import ConfigLoader
from .device_inventory import DeviceInventoryDetector
from .executor import ExecutionEngine
from .fc_probe import create_fc_adapter
from .fc_probe import FlightControllerProber
from .mission_log import MissionLog
from .planner.interfaces import LearnedPlanner, NullPlanner
from .planner.slm_planner import SLMPlanner
from .profile_store import ProfileStore
from .safety import SafetyGuard
from .schemas import MissionRequest, PlannerFeatures, RuntimeSnapshot, TelemetrySnapshot
from .supervisor import FCSupervisor, FlightPhase


class DroneRuntime:
    def __init__(
        self,
        detector: DeviceInventoryDetector | None = None,
        prober: FlightControllerProber | None = None,
        planner: LearnedPlanner | None = None,
        executor: ExecutionEngine | None = None,
        safety: SafetyGuard | None = None,
        profiles: ProfileStore | None = None,
        config: dict[str, Any] | None = None,
        config_path: str = "config.json",
        mission_log: MissionLog | None = None,
        slm_planner: SLMPlanner | None = None,
        fc_adapter: Any | None = None,
        supervisor: FCSupervisor | None = None,
        auto_create_config: bool = True,
    ) -> None:
        self.detector = detector or DeviceInventoryDetector()
        loader = ConfigLoader(config_path)
        self.config = config or (
            loader.load_or_create(detector=self.detector) if auto_create_config else loader.load()
        )
        self.prober = prober or FlightControllerProber()
        self.planner = planner or NullPlanner()
        self.executor = executor or ExecutionEngine()
        self.safety = safety or SafetyGuard(mission_behavior=self.config["mission_behavior"])
        profile_root = Path(self.config["logging"]["db_path"]).parent
        self.profiles = profiles or ProfileStore(profile_root)
        self.mission_log = mission_log or MissionLog(self.config["logging"]["db_path"])
        self.fc_adapter = fc_adapter or create_fc_adapter(self.config)
        self.slm_planner = slm_planner or SLMPlanner(self.config)
        self.supervisor = supervisor or FCSupervisor(self.fc_adapter, self.config)
        self.capability_profile: CapabilityProfile | None = None

    def boot(self) -> CapabilityProfile:
        """Load live FC state and build the current capability profile."""
        self.supervisor.reset()
        fc_capabilities = self.fc_adapter.probe()
        self.capability_profile = CapabilityProfile.from_config(self.config, fc_capabilities)
        self.mission_log.cleanup_old(self.config["logging"]["retain_days"])
        return self.capability_profile

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

    def plan_instruction(self, instruction: str, profile: CapabilityProfile | None = None) -> dict[str, Any]:
        """Create a structured procedure for a plain-text mission instruction."""
        profile = profile or self.capability_profile or self.boot()
        recent = self.mission_log.recent_missions(n=3)
        return self.slm_planner.plan(instruction, profile, recent)

    def run_instruction(self, instruction: str, dry_run: bool = False) -> dict[str, Any]:
        """Run the full config-driven mission pipeline for a single instruction."""
        profile = self.boot()
        procedure = self.plan_instruction(instruction, profile=profile)
        safety_report = self.safety.check(
            procedure.get("steps", []),
            profile,
            self.config["mission_behavior"],
        )
        result = {
            "plan": procedure,
            "safety": asdict(safety_report),
            "phase": self.supervisor.phase.value,
        }
        if dry_run:
            return result

        mission_id = self.mission_log.start_mission(
            instruction=instruction,
            task_type=procedure.get("task", "UNKNOWN"),
            battery_v=profile.fc.battery_voltage,
            config=self.config,
        )
        try:
            if safety_report.action in {"rtl", "abort"}:
                self._handle_terminal_action(mission_id, safety_report, procedure)
                result["phase"] = self.supervisor.phase.value
                return result

            blocked = set(safety_report.blocked_steps)
            for index, step in enumerate(procedure.get("steps", [])):
                if index in blocked:
                    status = "skipped"
                    detail = "blocked by safety guard"
                else:
                    execution = self.supervisor.execute_step(step, profile)
                    status = execution.status
                    detail = execution.detail
                self.mission_log.log_step(
                    mission_id,
                    step_index=index,
                    action=step.get("action", ""),
                    device=step.get("device", ""),
                    params={**step.get("params", {}), "detail": detail, "phase": self.supervisor.phase.value},
                    status=status,
                )
                if status != "skipped" and self.config["mission_behavior"]["log_sensor_data"]:
                    self._log_sensor_snapshot(mission_id, profile)
            outcome = "partial" if blocked or safety_report.warnings else "success"
            self.mission_log.end_mission(mission_id, outcome=outcome, battery_v=profile.fc.battery_voltage)
            self.supervisor.complete()
        except Exception:
            self.mission_log.end_mission(mission_id, outcome="aborted", battery_v=profile.fc.battery_voltage)
            raise
        result["phase"] = self.supervisor.phase.value
        return result

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

    def _handle_terminal_action(
        self,
        mission_id: int,
        safety_report: Any,
        procedure: dict[str, Any],
    ) -> None:
        action = safety_report.action
        if action in {"rtl", "abort"} and self.capability_profile is not None:
            execution = self.supervisor.execute_terminal_action(action, self.capability_profile)
            self.mission_log.log_step(
                mission_id,
                0,
                action,
                "fc",
                {"phase": self.supervisor.phase.value, "detail": execution.detail},
                execution.status,
            )
        self.mission_log.end_mission(
            mission_id,
            outcome="aborted" if action == "abort" else "partial",
            battery_v=self.capability_profile.fc.battery_voltage if self.capability_profile else None,
        )

    def _execute_step(self, step: dict[str, Any]) -> str:
        handler = self.executor.handlers.get(step.get("action", ""))
        if handler is None:
            return "failed"
        try:
            return "completed" if handler(step.get("action", "")) else "failed"
        except Exception:
            return "failed"

    def _log_sensor_snapshot(self, mission_id: int, profile: CapabilityProfile) -> None:
        interval = self.config["mission_behavior"]["log_interval_sec"]
        for sensor in profile.all_sensors():
            self.mission_log.log_sensor(
                mission_id,
                sensor_name=sensor["name"],
                value={
                    "available": sensor.get("available", True),
                    "type": sensor["type"],
                    "interval_sec": interval,
                },
            )
