from __future__ import annotations

import unittest

from dronepy.capability_profile import CapabilityProfile
from dronepy.schemas import FCCapabilities


class CapabilityProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "hardware": {
                "sensors": [
                    {"name": "camera", "type": "rgb_camera", "path": "/dev/video0"},
                    {"name": "thermal", "type": "MLX90640", "bus": "i2c-1"},
                    {"name": "gps", "type": "onboard_gps", "source": "mavlink"},
                ],
                "companion_computer": {"type": "raspberry_pi_4b", "ram_gb": 4},
            }
        }

    def test_profile_has_returns_correct_bool(self) -> None:
        fc = FCCapabilities(reachable=True, has_gps=True, gps_fix_type=3)
        profile = CapabilityProfile.from_config(self.config, fc)
        self.assertTrue(profile.has("camera"))
        self.assertTrue(profile.has("gps"))
        self.assertFalse(profile.has("lidar"))

    def test_profile_get_returns_sensor_dict(self) -> None:
        fc = FCCapabilities(reachable=True, has_gps=False, gps_fix_type=0)
        profile = CapabilityProfile.from_config(self.config, fc)
        sensor = profile.get("thermal")
        self.assertIsNotNone(sensor)
        self.assertEqual(sensor["type"], "MLX90640")

    def test_degraded_fc_is_handled_correctly(self) -> None:
        fc = FCCapabilities.degraded(protocol="mavlink", port="/dev/ttyUSB0", baud=57600)
        profile = CapabilityProfile.from_config(self.config, fc)
        self.assertFalse(profile.fc.reachable)
        self.assertFalse(profile.has("gps"))


if __name__ == "__main__":
    unittest.main()
