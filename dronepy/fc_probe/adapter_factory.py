"""Flight-controller adapter selection based on configured protocol."""

from __future__ import annotations

from typing import Any

from .dronecan_adapter import DroneCANAdapter
from .mavlink_adapter import MAVLinkAdapter
from .msp_adapter import MSPAdapter


def create_fc_adapter(config: dict[str, Any]):
    """Return the configured FC adapter instance."""
    fc_config = config["hardware"]["flight_controller"]
    protocol = fc_config["protocol"].lower()
    if protocol == "mavlink":
        return MAVLinkAdapter(port=fc_config["port"], baud=fc_config["baud"], protocol=protocol)
    if protocol == "msp":
        return MSPAdapter(port=fc_config["port"], baud=fc_config["baud"], protocol=protocol)
    if protocol == "dronecan":
        return DroneCANAdapter(port=fc_config["port"], baud=fc_config["baud"], protocol=protocol)
    raise ValueError(f"Unsupported flight-controller protocol: {fc_config['protocol']}")

