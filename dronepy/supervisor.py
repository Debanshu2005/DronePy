"""Mission-phase-aware supervisor for high-level FC and companion actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .capability_profile import CapabilityProfile


class FlightPhase(str, Enum):
    """High-level mission phases managed by the companion computer."""

    STARTING = "starting"
    READY = "ready"
    AIRBORNE = "airborne"
    LANDING = "landing"
    EMERGENCY = "emergency"
    COMPLETE = "complete"


@dataclass(slots=True)
class StepExecutionResult:
    """Result of executing a single mission step."""

    status: str
    phase: FlightPhase
    detail: str = ""


class FCSupervisor:
    """Translate high-level procedure steps into FC or companion actions."""

    FC_ACTIONS = {
        "arm",
        "disarm",
        "takeoff",
        "land",
        "rtl",
        "abort",
        "fly_pattern",
        "hold_position",
        "resume_mission",
    }

    LOCAL_ACTIONS = {
        "activate",
        "detect",
        "transmit",
        "log",
        "if_detection",
        "geotag",
    }

    def __init__(self, fc_adapter: Any, config: dict[str, Any]) -> None:
        self.fc_adapter = fc_adapter
        self.config = config
        self.phase = FlightPhase.STARTING

    def reset(self) -> None:
        """Reset supervisor state for a fresh mission."""
        self.phase = FlightPhase.STARTING

    def execute_step(self, step: dict[str, Any], profile: CapabilityProfile) -> StepExecutionResult:
        """Run one mission step against the FC or the companion stack."""
        action = str(step.get("action", "")).strip().lower()
        device = str(step.get("device", "")).strip().lower()
        params = step.get("params", {})

        if not action:
            return StepExecutionResult(status="failed", phase=self.phase, detail="missing action")

        if action in self.FC_ACTIONS or device == "fc":
            return self._execute_fc_action(action, params, profile)

        if action in self.LOCAL_ACTIONS:
            return self._execute_local_action(action, device, params, profile)

        return StepExecutionResult(status="failed", phase=self.phase, detail=f"unsupported action '{action}'")

    def execute_terminal_action(self, action: str, profile: CapabilityProfile) -> StepExecutionResult:
        """Handle abort/RTL-style supervisor overrides."""
        normalized = action.strip().lower()
        step = {"action": normalized, "device": "fc", "params": {}}
        return self.execute_step(step, profile)

    def complete(self) -> None:
        """Mark the mission as fully complete."""
        self.phase = FlightPhase.COMPLETE

    def _execute_fc_action(
        self,
        action: str,
        params: dict[str, Any],
        profile: CapabilityProfile,
    ) -> StepExecutionResult:
        if not profile.fc.reachable:
            self.phase = FlightPhase.EMERGENCY
            return StepExecutionResult(status="failed", phase=self.phase, detail="flight controller unreachable")

        dispatch_map = {
            "arm": ("arm", ()),
            "disarm": ("disarm", ()),
            "takeoff": ("takeoff", (float(params.get("altitude_m", self.config["mission_behavior"]["default_altitude_m"])),)),
            "land": ("land", ()),
            "rtl": ("rtl", ()),
            "abort": ("abort_mission", ()),
            "fly_pattern": ("start_mission_pattern", (params,)),
            "hold_position": ("hold_position", ()),
            "resume_mission": ("resume_mission", ()),
        }
        adapter_call = dispatch_map.get(action)
        if adapter_call is None:
            return StepExecutionResult(status="failed", phase=self.phase, detail=f"unsupported FC action '{action}'")

        method_name, args = adapter_call
        method = getattr(self.fc_adapter, method_name, None)
        if method is None:
            method = getattr(self.fc_adapter, "send_command", None)
            if method is None:
                return StepExecutionResult(status="failed", phase=self.phase, detail=f"adapter missing '{method_name}'")
            success = bool(method(action, params))
        else:
            try:
                success = bool(method(*args))
            except Exception:
                success = False

        self._advance_phase(action, success)
        status = "completed" if success else "failed"
        detail = "" if success else f"FC action '{action}' failed"
        return StepExecutionResult(status=status, phase=self.phase, detail=detail)

    def _execute_local_action(
        self,
        action: str,
        device: str,
        params: dict[str, Any],
        profile: CapabilityProfile,
    ) -> StepExecutionResult:
        if device and device != "fc" and not profile.has(device):
            return StepExecutionResult(
                status="skipped",
                phase=self.phase,
                detail=f"device '{device}' unavailable",
            )
        if action == "activate" and profile.fc.reachable:
            if self.phase == FlightPhase.STARTING:
                self.phase = FlightPhase.READY
        return StepExecutionResult(status="completed", phase=self.phase)

    def _advance_phase(self, action: str, success: bool) -> None:
        if not success:
            if action in {"abort", "rtl"}:
                self.phase = FlightPhase.EMERGENCY
            return

        if action == "arm":
            self.phase = FlightPhase.READY
        elif action in {"takeoff", "fly_pattern", "hold_position", "resume_mission"}:
            self.phase = FlightPhase.AIRBORNE
        elif action in {"land", "rtl"}:
            self.phase = FlightPhase.LANDING
        elif action == "abort":
            self.phase = FlightPhase.EMERGENCY

