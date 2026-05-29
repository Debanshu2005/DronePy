from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dronepy.config_autogen import AutoConfigBuilder
from dronepy.config_loader import ConfigError, ConfigLoader
from dronepy.device_inventory import DeviceInventoryDetector, StaticDeviceProvider
from dronepy.schemas import DetectedDevice


def build_config() -> dict:
    return {
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


class ConfigLoaderTests(unittest.TestCase):
    def test_valid_config_loads_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(json.dumps(build_config()), encoding="utf-8")
            data = ConfigLoader(path).load()
            self.assertEqual(data["hardware"]["flight_controller"]["protocol"], "mavlink")

    def test_missing_required_field_raises_clear_error(self) -> None:
        config = build_config()
        del config["hardware"]["flight_controller"]["port"]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "Missing required field: hardware.flight_controller.port"):
                ConfigLoader(path).load()

    def test_wrong_type_raises_clear_error(self) -> None:
        config = build_config()
        config["planner"]["max_tokens"] = "300"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "Wrong type for planner.max_tokens"):
                ConfigLoader(path).load()

    def test_missing_config_can_be_generated_from_scan(self) -> None:
        devices = [
            DetectedDevice(
                device_id="/dev/ttyUSB0",
                category="serial",
                transport="uart",
                name="Pixhawk 6C",
                metadata={"manufacturer": "Holybro"},
            ),
            DetectedDevice(
                device_id="/dev/video0",
                category="camera",
                transport="usb",
                name="Video device video0",
                metadata={"path": "/dev/video0"},
            ),
        ]
        detector = DeviceInventoryDetector([StaticDeviceProvider(devices)])
        fake_probe = {
            "controller_family": "PX4",
            "firmware_version": "1234",
            "has_gps": True,
            "gps_fix_type": 3,
            "has_barometer": True,
            "has_compass": True,
            "battery_voltage": 12.1,
            "armed": False,
            "reachable": True,
            "protocol": "mavlink",
            "port": "/dev/ttyUSB0",
            "baud": 57600,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            with unittest.mock.patch.object(AutoConfigBuilder, "_detect_flight_controller", return_value=(
                {
                    "type": "PX4",
                    "port": "/dev/ttyUSB0",
                    "baud": 57600,
                    "protocol": "mavlink",
                },
                __import__("dronepy.schemas", fromlist=["FCCapabilities"]).FCCapabilities(**fake_probe),
            )):
                data = ConfigLoader(path).load_or_create(detector=detector)
            self.assertTrue(path.exists())
            self.assertEqual(data["hardware"]["flight_controller"]["port"], "/dev/ttyUSB0")
            self.assertEqual(data["hardware"]["sensors"][0]["name"], "camera")


if __name__ == "__main__":
    unittest.main()
