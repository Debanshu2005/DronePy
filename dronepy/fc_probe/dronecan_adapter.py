"""DroneCAN adapter stub for future flight-controller support."""

from __future__ import annotations


class DroneCANAdapter:
    """Placeholder adapter for DroneCAN-based controllers."""

    def __init__(self, port: str, baud: int, protocol: str = "dronecan") -> None:
        self.port = port
        self.baud = baud
        self.protocol = protocol

    def probe(self):
        """DroneCAN support has not been implemented yet."""
        raise NotImplementedError("DroneCAN flight-controller probing is not implemented yet.")

    def send_command(self, command_name: str, params: dict | None = None) -> bool:
        """DroneCAN command bridge stub."""
        raise NotImplementedError("DroneCAN command dispatch is not implemented yet.")
