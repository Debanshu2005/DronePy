"""Shared prompt builder for DronePy planner training and inference."""

from __future__ import annotations

from typing import Any


def build_planner_prompt(
    instruction: str,
    controller_family: str,
    armed: bool,
    battery_voltage: float | None,
    sensors: list[dict[str, Any]],
    behavior: dict[str, Any],
    recent_missions: list[dict[str, Any]],
) -> str:
    """Build the exact prompt format expected by the DronePy planner."""
    device_list = ", ".join(f"{sensor['name']}({sensor['type']})" for sensor in sensors)

    past_context = ""
    for mission in recent_missions:
        past_context += (
            f"- {mission['task_type']}: {mission['outcome']} "
            f"(battery {mission['battery_start_v']}V->{mission['battery_end_v']}V)\n"
        )

    return f"""### Instruction:
{instruction}

### Hardware:
FC: {controller_family} | Armed: {armed}
Sensors: {device_list}
Battery: {battery_voltage}V

### Behavior Rules:
Default altitude: {behavior['default_altitude_m']}m
RTL on low battery: {behavior['rtl_on_low_battery']}
Battery cutoff: {behavior['battery_cutoff_voltage']}V
Max duration: {behavior['max_mission_duration_min']}min

### Recent Mission History:
{past_context or 'No previous missions.'}

### Response:"""
