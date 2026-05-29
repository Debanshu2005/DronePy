from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dronepy.mission_log import MissionLog
from dronepy.runtime import DroneRuntime
from dronepy.schemas import FCCapabilities


class FakeFCAdapter:
    def __init__(self, reachable: bool = True) -> None:
        self.reachable = reachable
        self.calls: list[tuple[str, object]] = []

    def probe(self) -> FCCapabilities:
        return FCCapabilities(
            controller_family="APM",
            firmware_version="1",
            has_gps=True,
            gps_fix_type=3,
            has_barometer=True,
            has_compass=True,
            battery_voltage=12.4,
            armed=True,
            reachable=self.reachable,
            protocol="mavlink",
            port="/dev/ttyUSB0",
            baud=57600,
        )

    def arm(self) -> bool:
        self.calls.append(("arm", None))
        return True

    def takeoff(self, altitude: float) -> bool:
        self.calls.append(("takeoff", altitude))
        return True

    def rtl(self) -> bool:
        self.calls.append(("rtl", None))
        return True

    def start_mission_pattern(self, params: dict) -> bool:
        self.calls.append(("fly_pattern", params))
        return True


class FakeSLMPlanner:
    def __init__(self, procedure: dict) -> None:
        self.procedure = procedure

    def plan(self, instruction: str, profile, recent_missions):
        return self.procedure


class SupervisorRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "hardware": {
                "flight_controller": {
                    "type": "APM2.8",
                    "port": "/dev/ttyUSB0",
                    "baud": 57600,
                    "protocol": "mavlink",
                },
                "sensors": [
                    {"name": "camera", "type": "rgb_camera", "path": "/dev/video0"},
                    {"name": "gps", "type": "onboard_gps", "source": "mavlink"},
                ],
                "companion_computer": {"type": "raspberry_pi_4b", "ram_gb": 4},
            },
            "mission_behavior": {
                "default_altitude_m": 30,
                "rtl_on_low_battery": True,
                "battery_cutoff_voltage": 10.5,
                "max_mission_duration_min": 20,
                "log_sensor_data": True,
                "log_interval_sec": 5,
            },
            "planner": {
                "model_path": "models/drone_slm.gguf",
                "fallback": "abort",
                "temperature": 0.1,
                "max_tokens": 300,
            },
            "logging": {"db_path": "logs/mission_log.db", "retain_days": 30},
        }

    def test_runtime_supervises_fc_actions(self) -> None:
        procedure = {
            "task": "SURVEY",
            "confidence": 0.9,
            "steps": [
                {"action": "arm", "device": "fc", "params": {}},
                {"action": "takeoff", "device": "fc", "params": {"altitude_m": 42}},
                {"action": "fly_pattern", "device": "fc", "params": {"pattern": "grid"}},
            ],
            "warning": None,
        }
        adapter = FakeFCAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = dict(self.config)
            config["logging"] = {"db_path": str(Path(temp_dir) / "mission_log.db"), "retain_days": 30}
            runtime = DroneRuntime(
                config=config,
                fc_adapter=adapter,
                slm_planner=FakeSLMPlanner(procedure),
                mission_log=MissionLog(config["logging"]["db_path"]),
            )
            result = runtime.run_instruction("survey field", dry_run=False)

        self.assertEqual(adapter.calls[0], ("arm", None))
        self.assertEqual(adapter.calls[1], ("takeoff", 42))
        self.assertEqual(adapter.calls[2], ("fly_pattern", {"pattern": "grid"}))
        self.assertEqual(result["phase"], "complete")

    def test_runtime_emergency_uses_rtl(self) -> None:
        procedure = {
            "task": "SURVEY",
            "confidence": 0.4,
            "steps": [{"action": "fly_pattern", "device": "fc", "params": {}}],
            "warning": None,
        }
        adapter = FakeFCAdapter()
        adapter.probe = lambda: FCCapabilities(
            controller_family="APM",
            battery_voltage=9.0,
            armed=True,
            reachable=True,
            protocol="mavlink",
            port="/dev/ttyUSB0",
            baud=57600,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config = dict(self.config)
            config["logging"] = {"db_path": str(Path(temp_dir) / "mission_log.db"), "retain_days": 30}
            runtime = DroneRuntime(
                config=config,
                fc_adapter=adapter,
                slm_planner=FakeSLMPlanner(procedure),
                mission_log=MissionLog(config["logging"]["db_path"]),
            )
            result = runtime.run_instruction("survey field", dry_run=False)

        self.assertIn(("rtl", None), adapter.calls)
        self.assertEqual(result["safety"]["action"], "rtl")
