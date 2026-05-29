"""Helpers for validating and formatting DronePy planner training examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = {
    "instruction",
    "hardware",
    "behavior",
    "recent_missions",
    "response",
}

REQUIRED_RESPONSE_FIELDS = {"task", "confidence", "steps", "warning"}
REQUIRED_STEP_FIELDS = {"action", "device", "params"}


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSONL dataset file into memory."""
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
        validate_example(record)
        records.append(record)
    return records


def validate_example(example: dict[str, Any]) -> None:
    """Raise ValueError if a training example does not match the required shape."""
    missing = REQUIRED_TOP_LEVEL - set(example)
    if missing:
        raise ValueError(f"Example missing required fields: {', '.join(sorted(missing))}")

    if not isinstance(example["instruction"], str) or not example["instruction"].strip():
        raise ValueError("Example instruction must be a non-empty string.")

    hardware = example["hardware"]
    if not isinstance(hardware, dict):
        raise ValueError("Example hardware must be an object.")
    if "fc" not in hardware or "sensors" not in hardware:
        raise ValueError("Example hardware must include 'fc' and 'sensors'.")
    if not isinstance(hardware["sensors"], list):
        raise ValueError("Example hardware.sensors must be a list.")

    response = example["response"]
    if not isinstance(response, dict):
        raise ValueError("Example response must be an object.")
    missing_response = REQUIRED_RESPONSE_FIELDS - set(response)
    if missing_response:
        raise ValueError(f"Example response missing fields: {', '.join(sorted(missing_response))}")
    if not isinstance(response["steps"], list):
        raise ValueError("Example response.steps must be a list.")
    for index, step in enumerate(response["steps"]):
        if not isinstance(step, dict):
            raise ValueError(f"Step {index} must be an object.")
        missing_step = REQUIRED_STEP_FIELDS - set(step)
        if missing_step:
            raise ValueError(f"Step {index} missing fields: {', '.join(sorted(missing_step))}")


def build_prompt(example: dict[str, Any]) -> str:
    """Build the exact planner prompt format used by DronePy."""
    validate_example(example)

    fc = example["hardware"]["fc"]
    sensors = example["hardware"]["sensors"]
    behavior = example["behavior"]
    recent_missions = example["recent_missions"]

    device_list = ", ".join(f"{sensor['name']}({sensor['type']})" for sensor in sensors)

    past_context = ""
    for mission in recent_missions:
        past_context += (
            f"- {mission['task_type']}: {mission['outcome']} "
            f"(battery {mission['battery_start_v']}V->{mission['battery_end_v']}V)\n"
        )

    return f"""### Instruction:
{example['instruction']}

### Hardware:
FC: {fc['controller_family']} | Armed: {fc['armed']}
Sensors: {device_list}
Battery: {fc['battery_voltage']}V

### Behavior Rules:
Default altitude: {behavior['default_altitude_m']}m
RTL on low battery: {behavior['rtl_on_low_battery']}
Battery cutoff: {behavior['battery_cutoff_voltage']}V
Max duration: {behavior['max_mission_duration_min']}min

### Recent Mission History:
{past_context or 'No previous missions.'}

### Response:"""


def format_supervised_text(example: dict[str, Any]) -> str:
    """Return a single text sample ready for instruction fine-tuning."""
    prompt = build_prompt(example)
    response = json.dumps(example["response"], indent=2, sort_keys=True)
    return f"{prompt}\n{response}"

