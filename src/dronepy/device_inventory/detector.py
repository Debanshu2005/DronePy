from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from ..schemas import DetectedDevice


class DeviceProvider(Protocol):
    def scan(self) -> list[DetectedDevice]:
        """Return detected devices for a given transport or subsystem."""


class StaticDeviceProvider:
    def __init__(self, devices: list[DetectedDevice]) -> None:
        self._devices = devices

    def scan(self) -> list[DetectedDevice]:
        return list(self._devices)


class SerialPortProvider:
    """Best-effort serial enumeration without forcing pyserial."""

    def scan(self) -> list[DetectedDevice]:
        try:
            from serial.tools import list_ports
        except ImportError:
            return []

        devices: list[DetectedDevice] = []
        for port in list_ports.comports():
            metadata = {
                "manufacturer": port.manufacturer,
                "product": port.product,
                "vid": port.vid,
                "pid": port.pid,
                "serial_number": port.serial_number,
            }
            devices.append(
                DetectedDevice(
                    device_id=port.device,
                    category="serial",
                    transport="uart",
                    name=port.description or port.device,
                    metadata={k: v for k, v in metadata.items() if v is not None},
                )
            )
        return devices


class DeviceInventoryDetector:
    def __init__(self, providers: list[DeviceProvider] | None = None) -> None:
        self.providers = providers or [SerialPortProvider()]

    def detect(self) -> list[DetectedDevice]:
        merged: dict[str, DetectedDevice] = {}
        for provider in self.providers:
            for device in provider.scan():
                key = device.device_id
                if key in merged:
                    existing = merged[key]
                    merged[key] = replace(
                        existing,
                        metadata={**existing.metadata, **device.metadata},
                    )
                    continue
                merged[key] = device
        return sorted(merged.values(), key=lambda device: (device.category, device.device_id))

