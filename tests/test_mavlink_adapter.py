from __future__ import annotations

from types import ModuleType, SimpleNamespace
from unittest import mock
import unittest

from dronepy.fc_probe.mavlink_adapter import MAVLinkAdapter


class FakeConnection:
    def __init__(self, messages: dict[str, object], heartbeat: object | None) -> None:
        self.messages = messages
        self._heartbeat = heartbeat
        self.mav = SimpleNamespace(command_long_send=lambda *args, **kwargs: None)

    def wait_heartbeat(self, timeout: int | None = None):
        return self._heartbeat

    def recv_match(self, type: str, blocking: bool = True, timeout: int | None = None):
        return self.messages.get(type)


class MAVLinkAdapterTests(unittest.TestCase):
    def test_successful_probe_returns_capabilities(self) -> None:
        heartbeat = SimpleNamespace(autopilot=3, base_mode=0b10000000)
        messages = {
            "HEARTBEAT": heartbeat,
            "SYS_STATUS": SimpleNamespace(onboard_control_sensors_present=(1 << 3) | (1 << 2), voltage_battery=12000),
            "AUTOPILOT_VERSION": SimpleNamespace(flight_sw_version=123456),
            "BATTERY_STATUS": SimpleNamespace(voltages=[12000]),
            "GPS_RAW_INT": SimpleNamespace(fix_type=3),
            "ATTITUDE": SimpleNamespace(),
        }
        fake_connection = FakeConnection(messages, heartbeat)
        fake_mavutil = SimpleNamespace(mavlink_connection=lambda port, baud: fake_connection)
        fake_package = ModuleType("pymavlink")
        fake_package.mavutil = fake_mavutil

        with mock.patch.dict("sys.modules", {"pymavlink": fake_package}):
            adapter = MAVLinkAdapter("/dev/ttyUSB0", 57600)
            result = adapter.probe()

        self.assertEqual(result.controller_family, "APM")
        self.assertTrue(result.reachable)
        self.assertTrue(result.has_gps)
        self.assertEqual(result.gps_fix_type, 3)
        self.assertAlmostEqual(result.battery_voltage, 12.0)
        self.assertTrue(result.armed)

    def test_timeout_returns_degraded_capabilities(self) -> None:
        fake_connection = FakeConnection({}, None)
        fake_mavutil = SimpleNamespace(mavlink_connection=lambda port, baud: fake_connection)
        fake_package = ModuleType("pymavlink")
        fake_package.mavutil = fake_mavutil

        with mock.patch.dict("sys.modules", {"pymavlink": fake_package}):
            adapter = MAVLinkAdapter("/dev/ttyUSB0", 57600)
            result = adapter.probe()

        self.assertFalse(result.reachable)
        self.assertFalse(result.has_gps)
        self.assertFalse(result.armed)


if __name__ == "__main__":
    unittest.main()
