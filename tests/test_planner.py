from __future__ import annotations

from unittest import mock
import unittest

from dronepy.capability_profile import CapabilityProfile
from dronepy.planner.interfaces import NullPlanner
from dronepy.planner.slm_planner import SLMPlanner
from dronepy.schemas import FCCapabilities, MissionRequest, PlannerFeatures, TelemetrySnapshot


class FakeLlama:
    def __init__(self, *args, **kwargs) -> None:
        self.responses = kwargs.pop("responses", [])

    def create_completion(self, prompt: str, temperature: float, max_tokens: int) -> dict:
        return {"choices": [{"text": self.responses.pop(0)}]}


def build_profile() -> CapabilityProfile:
    config = {
        "hardware": {
            "sensors": [{"name": "camera", "type": "rgb_camera", "path": "/dev/video0"}],
            "companion_computer": {"type": "raspberry_pi_4b", "ram_gb": 4},
        }
    }
    fc = FCCapabilities(reachable=True, controller_family="APM", battery_voltage=12.1)
    return CapabilityProfile.from_config(config, fc)


def build_config() -> dict:
    return {
        "hardware": {
            "flight_controller": {
                "type": "APM2.8",
                "port": "/dev/ttyUSB0",
                "baud": 57600,
                "protocol": "mavlink",
            },
            "sensors": [{"name": "camera", "type": "rgb_camera", "path": "/dev/video0"}],
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


class PlannerTests(unittest.TestCase):
    def test_null_planner_regression(self) -> None:
        planner = NullPlanner()
        features = PlannerFeatures(
            request=MissionRequest(text="monitor crops"),
            devices=[],
            controller=None,
            telemetry=TelemetrySnapshot(),
        )
        plan = planner.plan(features)
        self.assertEqual(plan.intent, "planner_unavailable")

    def test_slm_planner_with_mocked_llama_returns_valid_plan(self) -> None:
        config = build_config()
        valid_json = '{"task":"SURVEY","confidence":0.9,"steps":[{"action":"activate","device":"camera","params":{"mode":"rgb"}}],"warning":null}'
        fake_llm = mock.Mock()
        fake_llm.create_completion.return_value = {"choices": [{"text": valid_json}]}

        with mock.patch("dronepy.planner.slm_planner.Llama", return_value=fake_llm):
            planner = SLMPlanner(config)
            result = planner.plan("monitor crops", build_profile(), [])

        self.assertEqual(result["task"], "SURVEY")
        self.assertEqual(result["steps"][0]["device"], "camera")

    def test_invalid_json_returns_fallback_rtl_plan(self) -> None:
        config = build_config()
        fake_llm = mock.Mock()
        fake_llm.create_completion.side_effect = [
            {"choices": [{"text": "not json"}]},
            {"choices": [{"text": "still not json"}]},
        ]

        with mock.patch("dronepy.planner.slm_planner.Llama", return_value=fake_llm):
            planner = SLMPlanner(config)
            result = planner.plan("monitor crops", build_profile(), [])

        self.assertEqual(result["task"], "ABORT")
        self.assertEqual(result["steps"][0]["action"], "rtl")


if __name__ == "__main__":
    unittest.main()
