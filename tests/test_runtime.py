from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from dronepy.device_inventory import DeviceInventoryDetector, StaticDeviceProvider
from dronepy.executor import ExecutionEngine
from dronepy.fc_probe import FlightControllerProber
from dronepy.planner.interfaces import LearnedPlanner
from dronepy.profile_store import ProfileStore
from dronepy.runtime import DroneRuntime
from dronepy.safety import SafetyGuard
from dronepy.schemas import DetectedDevice, MissionPlan, MissionRequest, PlannerFeatures, TelemetrySnapshot


class FakePlanner(LearnedPlanner):
    def plan(self, features: PlannerFeatures) -> MissionPlan:
        return MissionPlan(
            plan_id=str(uuid4()),
            intent="track_and_stream",
            actions=["arm", "takeoff"],
            required_capabilities=["arm", "takeoff"],
            confidence=0.92,
            metadata={"request": features.request.text},
        )


class RuntimeTests(unittest.TestCase):
    def test_runtime_detects_controller_and_executes_plan(self) -> None:
        devices = [
            DetectedDevice(
                device_id="/dev/ttyACM0",
                category="serial",
                transport="uart",
                name="Pixhawk 6C",
                metadata={"manufacturer": "Holybro"},
            )
        ]
        detector = DeviceInventoryDetector([StaticDeviceProvider(devices)])
        executor = ExecutionEngine({"arm": lambda action: True, "takeoff": lambda action: True})

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = DroneRuntime(
                detector=detector,
                prober=FlightControllerProber(),
                planner=FakePlanner(),
                executor=executor,
                safety=SafetyGuard(),
                profiles=ProfileStore(Path(temp_dir)),
            )
            snapshot = runtime.inspect(TelemetrySnapshot(battery_percent=64, link_quality=0.9))
            self.assertIsNotNone(snapshot.controller)
            self.assertEqual(snapshot.controller.family, "PX4")

            report = runtime.execute(
                MissionRequest(text="take off and follow target"),
                snapshot=snapshot,
            )
            self.assertTrue(report.safety.approved)
            self.assertEqual(report.executed_actions, ["arm", "takeoff"])
            self.assertEqual(report.failed_actions, [])

    def test_safety_blocks_low_battery(self) -> None:
        devices = [
            DetectedDevice(
                device_id="/dev/ttyACM0",
                category="serial",
                transport="uart",
                name="Cube Orange",
            )
        ]
        detector = DeviceInventoryDetector([StaticDeviceProvider(devices)])
        executor = ExecutionEngine({"arm": lambda action: True})

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = DroneRuntime(
                detector=detector,
                planner=FakePlanner(),
                executor=executor,
                profiles=ProfileStore(Path(temp_dir)),
            )
            snapshot = runtime.inspect(TelemetrySnapshot(battery_percent=5, link_quality=0.9))
            report = runtime.execute(MissionRequest(text="arm now"), snapshot=snapshot)
            self.assertFalse(report.safety.approved)
            self.assertIn("battery below safety threshold", report.safety.reasons)


if __name__ == "__main__":
    unittest.main()
