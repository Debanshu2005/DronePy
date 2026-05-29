from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from ..schemas import CapabilityEvidence, DetectedDevice, FlightControllerProfile


class ProbeAdapter(Protocol):
    def probe(self, devices: list[DetectedDevice]) -> FlightControllerProfile | None:
        """Return a normalized controller profile if this adapter can identify one."""


class KeywordProbeAdapter:
    """
    Lightweight identifier for development setups.

    Real deployments should replace or extend this with MAVLink, DroneCAN,
    and vendor-specific live probes.
    """

    KEYWORDS = {
        "px4": {
            "family": "PX4",
            "capabilities": ["arm", "disarm", "takeoff", "land", "rtl", "telemetry"],
            "modes": ["manual", "position", "mission", "offboard"],
        },
        "pixhawk": {
            "family": "PX4",
            "capabilities": ["arm", "disarm", "takeoff", "land", "rtl", "telemetry"],
            "modes": ["manual", "position", "mission", "offboard"],
        },
        "ardupilot": {
            "family": "ArduPilot",
            "capabilities": ["arm", "disarm", "takeoff", "land", "rtl", "mission_upload", "telemetry"],
            "modes": ["stabilize", "loiter", "auto", "guided"],
        },
        "cube": {
            "family": "ArduPilot",
            "capabilities": ["arm", "disarm", "takeoff", "land", "rtl", "mission_upload", "telemetry"],
            "modes": ["stabilize", "loiter", "auto", "guided"],
        },
        "betaflight": {
            "family": "Betaflight",
            "capabilities": ["arm", "disarm", "telemetry"],
            "modes": ["acro", "angle", "horizon"],
        },
        "inav": {
            "family": "INAV",
            "capabilities": ["arm", "disarm", "rtl", "telemetry"],
            "modes": ["acro", "angle", "nav"],
        },
    }

    def probe(self, devices: list[DetectedDevice]) -> FlightControllerProfile | None:
        for device in devices:
            text = " ".join(
                [
                    device.name,
                    str(device.metadata.get("manufacturer", "")),
                    str(device.metadata.get("product", "")),
                ]
            ).lower()
            for keyword, info in self.KEYWORDS.items():
                if keyword not in text:
                    continue
                evidence = [
                    CapabilityEvidence(
                        capability=capability,
                        source=f"keyword:{keyword}",
                        confidence=0.55,
                    )
                    for capability in info["capabilities"]
                ]
                return FlightControllerProfile(
                    controller_id=device.device_id,
                    family=info["family"],
                    transport=device.transport,
                    capabilities=list(info["capabilities"]),
                    modes=list(info["modes"]),
                    telemetry_topics=["heartbeat"],
                    confidence=0.55,
                    evidence=evidence,
                    metadata={"device_name": device.name, "probe": "keyword"},
                )
        return None


class FlightControllerProber:
    def __init__(self, adapters: list[ProbeAdapter] | None = None) -> None:
        self.adapters = adapters or [KeywordProbeAdapter()]

    def probe(self, devices: list[DetectedDevice]) -> FlightControllerProfile | None:
        best: FlightControllerProfile | None = None
        for adapter in self.adapters:
            profile = adapter.probe(devices)
            if profile is None:
                continue
            if best is None or profile.confidence > best.confidence:
                best = profile
        return best

    def merge_observations(
        self,
        profile: FlightControllerProfile,
        observed_capabilities: list[str],
    ) -> FlightControllerProfile:
        capabilities = set(profile.capabilities)
        evidence = list(profile.evidence)
        for capability in observed_capabilities:
            if capability in capabilities:
                continue
            capabilities.add(capability)
            evidence.append(
                CapabilityEvidence(
                    capability=capability,
                    source="observed-outcome",
                    confidence=0.9,
                )
            )
        return replace(
            profile,
            capabilities=sorted(capabilities),
            confidence=min(1.0, profile.confidence + 0.1),
            evidence=evidence,
        )

