from __future__ import annotations

import unittest

from dronepy.capability_profile import CapabilityProfile
from dronepy.safety import SafetyGuard
from dronepy.schemas import FCCapabilities


def build_profile(fc: FCCapabilities) -> CapabilityProfile:
    config = {
        "hardware": {
            "sensors": [
                {"name": "camera", "type": "rgb_camera", "path": "/dev/video0"},
                {"name": "gps", "type": "onboard_gps", "source": "mavlink"},
            ],
            "companion_computer": {"type": "raspberry_pi_4b", "ram_gb": 4},
        }
    }
    return CapabilityProfile.from_config(config, fc)


class SafetyGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.behavior = {"battery_cutoff_voltage": 10.5}
        self.guard = SafetyGuard(mission_behavior=self.behavior)

    def test_low_battery_returns_rtl(self) -> None:
        profile = build_profile(FCCapabilities(reachable=True, battery_voltage=9.9))
        report = self.guard.check([{"action": "fly_pattern", "device": "fc", "params": {}}], profile, self.behavior)
        self.assertEqual(report.action, "rtl")

    def test_missing_device_blocks_step_with_warning(self) -> None:
        profile = build_profile(FCCapabilities(reachable=True, battery_voltage=12.0, armed=True, has_gps=True, gps_fix_type=3))
        steps = [{"action": "detect", "device": "thermal", "params": {}}]
        report = self.guard.check(steps, profile, self.behavior)
        self.assertEqual(report.action, "proceed_with_warnings")
        self.assertEqual(report.blocked_steps, [0])

    def test_fc_unreachable_returns_abort(self) -> None:
        profile = build_profile(FCCapabilities.degraded(protocol="mavlink", port="/dev/ttyUSB0", baud=57600))
        report = self.guard.check([{"action": "activate", "device": "camera", "params": {}}], profile, self.behavior)
        self.assertEqual(report.action, "abort")

    def test_all_clear_returns_proceed(self) -> None:
        profile = build_profile(FCCapabilities(reachable=True, battery_voltage=12.0, armed=True, has_gps=True, gps_fix_type=3))
        steps = [{"action": "fly_pattern", "device": "fc", "params": {}}]
        report = self.guard.check(steps, profile, self.behavior)
        self.assertEqual(report.action, "proceed")


if __name__ == "__main__":
    unittest.main()
