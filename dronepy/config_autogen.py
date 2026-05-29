"""Automatic config generation from local device scan and MAVLink probing."""

from __future__ import annotations

from copy import deepcopy
import platform
from pathlib import Path
from typing import Any

from .device_inventory import DeviceInventoryDetector
from .fc_probe.mavlink_adapter import MAVLinkAdapter
from .schemas import DetectedDevice, FCCapabilities


class AutoConfigBuilder:
    """Generate a DronePy config from detected local devices and a live FC probe."""

    COMMON_BAUD_RATES = (57600, 115200)

    def __init__(self, detector: DeviceInventoryDetector | None = None) -> None:
        self.detector = detector or DeviceInventoryDetector()

    def generate(self) -> dict[str, Any]:
        """Return a generated config dictionary based on scanned hardware."""
        devices = self.detector.detect()
        fc_config, fc_capabilities = self._detect_flight_controller(devices)
        sensors = self._detect_sensors(devices, fc_capabilities)
        return {
            "hardware": {
                "flight_controller": fc_config,
                "sensors": sensors,
                "companion_computer": self._companion_info(),
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
            "logging": {
                "db_path": "logs/mission_log.db",
                "retain_days": 30,
            },
        }

    def save(self, path: str | Path, config: dict[str, Any]) -> None:
        """Persist a generated config to disk."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        import json

        target.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")

    def _detect_flight_controller(self, devices: list[DetectedDevice]) -> tuple[dict[str, Any], FCCapabilities]:
        serial_devices = [device for device in devices if device.category == "serial"]
        best_device = serial_devices[0] if serial_devices else None
        best_capabilities = FCCapabilities.degraded(protocol="mavlink")

        for device in serial_devices:
            for baud in self.COMMON_BAUD_RATES:
                capabilities = MAVLinkAdapter(
                    port=device.device_id,
                    baud=baud,
                    protocol="mavlink",
                    timeout=2,
                ).probe()
                if not capabilities.reachable:
                    continue
                best_device = device
                best_capabilities = capabilities
                return (
                    {
                        "type": capabilities.controller_family or device.name,
                        "port": device.device_id,
                        "baud": baud,
                        "protocol": "mavlink",
                    },
                    capabilities,
                )

        if best_device is None:
            return (
                {
                    "type": "unknown_fc",
                    "port": "/dev/ttyUSB0",
                    "baud": 57600,
                    "protocol": "mavlink",
                },
                best_capabilities,
            )
        return (
            {
                "type": best_device.name or "unknown_fc",
                "port": best_device.device_id,
                "baud": 57600,
                "protocol": "mavlink",
            },
            best_capabilities,
        )

    def _detect_sensors(
        self,
        devices: list[DetectedDevice],
        fc_capabilities: FCCapabilities,
    ) -> list[dict[str, Any]]:
        sensors: list[dict[str, Any]] = []
        seen: set[str] = set()

        for device in devices:
            sensor = self._device_to_sensor(device)
            if sensor is None:
                continue
            if sensor["name"] in seen:
                continue
            sensors.append(sensor)
            seen.add(sensor["name"])

        if fc_capabilities.has_gps and "gps" not in seen:
            sensors.append({"name": "gps", "type": "onboard_gps", "source": "mavlink"})
            seen.add("gps")

        if not sensors:
            sensors.append({"name": "gps", "type": "onboard_gps", "source": "mavlink"})
        return sensors

    @staticmethod
    def _device_to_sensor(device: DetectedDevice) -> dict[str, Any] | None:
        name_text = device.name.lower()
        metadata = deepcopy(device.metadata)

        if device.category == "camera":
            path = metadata.get("path", device.device_id)
            return {
                "name": "camera",
                "type": "rgb_camera",
                "path": path,
            }
        if "thermal" in name_text or "mlx90640" in name_text:
            return {
                "name": "thermal",
                "type": "MLX90640",
                "bus": metadata.get("bus", "i2c-1"),
                "address": metadata.get("address", "0x33"),
            }
        if "mpu6050" in name_text or "imu" in name_text:
            return {
                "name": "imu",
                "type": "MPU6050",
                "bus": metadata.get("bus", "i2c-1"),
                "address": metadata.get("address", "0x68"),
            }
        if "sx127" in name_text or "lora" in name_text:
            return {
                "name": "lora",
                "type": "SX127x",
                "bus": metadata.get("bus", "spi0"),
            }
        return None

    @staticmethod
    def _companion_info() -> dict[str, Any]:
        ram_gb = 4
        try:
            page_size = int(Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()[0].split()[1])
            ram_gb = max(1, round(page_size / 1024 / 1024))
        except Exception:
            try:
                import os

                if hasattr(os, "sysconf"):
                    pages = os.sysconf("SC_PHYS_PAGES")
                    page_size = os.sysconf("SC_PAGE_SIZE")
                    ram_gb = max(1, round((pages * page_size) / (1024**3)))
            except Exception:
                ram_gb = 4
        machine = platform.machine().lower()
        device_type = "raspberry_pi_4b" if "arm" in machine or "aarch" in machine else "generic_companion"
        return {"type": device_type, "ram_gb": ram_gb}
