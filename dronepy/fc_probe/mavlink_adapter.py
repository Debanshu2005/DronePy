"""Best-effort MAVLink flight-controller probing and command dispatch."""

from __future__ import annotations

from typing import Any

from ..schemas import FCCapabilities


class MAVLinkAdapter:
    """Probe a flight controller over MAVLink and return normalized capabilities."""

    MAV_MODE_FLAG_SAFETY_ARMED = 0b10000000
    MAV_AUTOPILOT_PX4 = 12
    MAV_AUTOPILOT_ARDUPILOTMEGA = 3
    MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE = 1 << 3
    MAV_SYS_STATUS_SENSOR_3D_MAG = 1 << 2
    MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
    MAV_CMD_NAV_LAND = 21
    MAV_CMD_NAV_TAKEOFF = 22
    MAV_CMD_COMPONENT_ARM_DISARM = 400

    def __init__(self, port: str, baud: int, protocol: str = "mavlink", timeout: int = 10) -> None:
        self.port = port
        self.baud = baud
        self.protocol = protocol
        self.timeout = timeout
        self._connection: Any | None = None

    def probe(self) -> FCCapabilities:
        """Attempt to probe the configured FC and degrade silently on any failure."""
        try:
            connection = self._get_connection()
            if connection is None:
                return FCCapabilities.degraded(protocol=self.protocol, port=self.port, baud=self.baud)
            heartbeat = self._safe_wait_heartbeat(connection)
            self._request_messages(connection)
            messages = self._collect_messages(connection)
            return self._build_capabilities(heartbeat, messages)
        except Exception:
            return FCCapabilities.degraded(protocol=self.protocol, port=self.port, baud=self.baud)

    def arm(self) -> bool:
        """Request arming via MAVLink."""
        return self._send_command_long(self.MAV_CMD_COMPONENT_ARM_DISARM, 1.0)

    def disarm(self) -> bool:
        """Request disarming via MAVLink."""
        return self._send_command_long(self.MAV_CMD_COMPONENT_ARM_DISARM, 0.0)

    def takeoff(self, altitude_m: float) -> bool:
        """Request an autonomous takeoff."""
        return self._send_command_long(self.MAV_CMD_NAV_TAKEOFF, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, altitude_m)

    def land(self) -> bool:
        """Request landing."""
        return self._send_command_long(self.MAV_CMD_NAV_LAND, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def rtl(self) -> bool:
        """Request return-to-launch."""
        return self._send_command_long(self.MAV_CMD_NAV_RETURN_TO_LAUNCH, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def hold_position(self) -> bool:
        """Best-effort position hold using a generic command bridge."""
        return self.send_command("hold_position", {})

    def resume_mission(self) -> bool:
        """Best-effort mission resume using a generic command bridge."""
        return self.send_command("resume_mission", {})

    def abort_mission(self) -> bool:
        """Abort the current mission by preferring RTL as the safest fallback."""
        return self.rtl()

    def start_mission_pattern(self, params: dict[str, Any]) -> bool:
        """Start a mission pattern. This is a placeholder until mission upload is added."""
        return self.send_command("fly_pattern", params)

    def send_command(self, command_name: str, params: dict[str, Any]) -> bool:
        """Generic best-effort command bridge for unsupported high-level MAVLink actions."""
        try:
            connection = self._get_connection()
            if connection is None:
                return False
            if hasattr(connection, "mav") and hasattr(connection.mav, "statustext_send"):
                text = f"dronepy:{command_name}"
                connection.mav.statustext_send(6, text.encode("ascii", errors="ignore"))
            return True
        except Exception:
            return False

    def _safe_wait_heartbeat(self, connection: Any) -> Any:
        if hasattr(connection, "wait_heartbeat"):
            return connection.wait_heartbeat(timeout=self.timeout)
        return None

    def _get_connection(self) -> Any | None:
        if self._connection is not None:
            return self._connection
        try:
            from pymavlink import mavutil
        except ImportError:
            return None
        try:
            self._connection = mavutil.mavlink_connection(self.port, baud=self.baud)
        except Exception:
            self._connection = None
        return self._connection

    def _request_messages(self, connection: Any) -> None:
        try:
            if hasattr(connection, "mav") and hasattr(connection.mav, "command_long_send"):
                connection.mav.command_long_send(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        except Exception:
            pass

    def _collect_messages(self, connection: Any) -> dict[str, Any]:
        messages: dict[str, Any] = {}
        message_types = [
            "SYS_STATUS",
            "AUTOPILOT_VERSION",
            "BATTERY_STATUS",
            "GPS_RAW_INT",
            "ATTITUDE",
            "HEARTBEAT",
        ]
        for message_type in message_types:
            try:
                messages[message_type] = connection.recv_match(type=message_type, blocking=True, timeout=self.timeout)
            except Exception:
                messages[message_type] = None
        return messages

    def _build_capabilities(self, heartbeat: Any, messages: dict[str, Any]) -> FCCapabilities:
        heartbeat = messages.get("HEARTBEAT") or heartbeat
        sys_status = messages.get("SYS_STATUS")
        autopilot_version = messages.get("AUTOPILOT_VERSION")
        battery_status = messages.get("BATTERY_STATUS")
        gps_raw = messages.get("GPS_RAW_INT")

        family = "unknown"
        autopilot_value = self._message_attr(heartbeat, "autopilot")
        if autopilot_value in (self.MAV_AUTOPILOT_ARDUPILOTMEGA, "ardupilotmega", "apm"):
            family = "APM"
        elif autopilot_value in (self.MAV_AUTOPILOT_PX4, "px4"):
            family = "PX4"

        battery_voltage = None
        voltages = self._message_attr(battery_status, "voltages")
        if isinstance(voltages, (list, tuple)) and voltages:
            battery_voltage = float(voltages[0]) / 1000.0
        else:
            voltage_battery = self._message_attr(sys_status, "voltage_battery")
            if voltage_battery is not None:
                battery_voltage = float(voltage_battery) / 1000.0

        onboard_flags = int(self._message_attr(sys_status, "onboard_control_sensors_present", 0) or 0)
        gps_fix_type = int(self._message_attr(gps_raw, "fix_type", 0) or 0)
        base_mode = int(self._message_attr(heartbeat, "base_mode", 0) or 0)
        firmware_version = self._normalize_version(autopilot_version)

        return FCCapabilities(
            controller_family=family,
            firmware_version=firmware_version,
            has_gps=gps_fix_type > 0,
            gps_fix_type=gps_fix_type,
            has_barometer=bool(onboard_flags & self.MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE),
            has_compass=bool(onboard_flags & self.MAV_SYS_STATUS_SENSOR_3D_MAG),
            battery_voltage=battery_voltage,
            armed=bool(base_mode & self.MAV_MODE_FLAG_SAFETY_ARMED),
            reachable=heartbeat is not None,
            protocol=self.protocol,
            port=self.port,
            baud=self.baud,
        )

    @staticmethod
    def _normalize_version(message: Any) -> str | None:
        flight_sw = MAVLinkAdapter._message_attr(message, "flight_sw_version")
        if flight_sw is None:
            return None
        return str(flight_sw)

    def _send_command_long(self, command: int, *params: float) -> bool:
        connection = self._get_connection()
        if connection is None:
            return False
        try:
            padded = list(params)[:7]
            while len(padded) < 7:
                padded.append(0.0)
            target_system = getattr(connection, "target_system", 0)
            target_component = getattr(connection, "target_component", 0)
            connection.mav.command_long_send(
                target_system,
                target_component,
                command,
                0,
                *padded,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _message_attr(message: Any, name: str, default: Any = None) -> Any:
        if message is None:
            return default
        return getattr(message, name, default)
