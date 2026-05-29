"""MSP adapter stub for future flight-controller support."""

from __future__ import annotations


class MSPAdapter:
    """Placeholder adapter for MSP-based controllers."""

    def __init__(self, port: str, baud: int, protocol: str = "msp") -> None:
        self.port = port
        self.baud = baud
        self.protocol = protocol

    def probe(self):
        """MSP support has not been implemented yet."""
        raise NotImplementedError("MSP flight-controller probing is not implemented yet.")

    def send_command(self, command_name: str, params: dict | None = None) -> bool:
        """MSP command bridge stub."""
        raise NotImplementedError("MSP command dispatch is not implemented yet.")
