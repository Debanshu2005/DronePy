"""Offline small-language-model planner for structured mission procedures."""

from __future__ import annotations

import json
from typing import Any

from ..capability_profile import CapabilityProfile
from .prompt_builder import build_planner_prompt

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover - exercised via fallback tests
    Llama = None


def build_prompt(
    instruction: str,
    profile: CapabilityProfile,
    recent_missions: list[dict[str, Any]],
    behavior: dict[str, Any],
) -> str:
    """Build the planner prompt from instruction, hardware, and mission history."""
    return build_planner_prompt(
        instruction=instruction,
        controller_family=profile.fc.controller_family,
        armed=profile.fc.armed,
        battery_voltage=profile.fc.battery_voltage,
        sensors=profile.all_sensors(),
        behavior=behavior,
        recent_missions=recent_missions,
    )


class SLMPlanner:
    """Use a local GGUF model to create structured offline mission procedures."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.behavior = config["mission_behavior"]
        self.planner_config = config["planner"]
        self.llm = self._load_model()

    def _load_model(self):
        if Llama is None:
            return None
        try:
            return Llama(
                model_path=self.planner_config["model_path"],
                n_ctx=512,
                n_threads=4,
                verbose=False,
            )
        except Exception:
            return None

    def plan(
        self,
        instruction: str,
        profile: CapabilityProfile,
        recent_missions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return a JSON-serializable mission procedure."""
        prompt = build_prompt(instruction, profile, recent_missions, self.behavior)
        fallback = self._fallback_plan("Planner failed to generate valid output")
        if self.llm is None:
            return fallback

        result = self._run_completion(prompt)
        parsed = self._parse_json(result)
        if parsed is not None:
            return parsed

        strict_prompt = (
            prompt
            + "\nRespond with valid JSON only, no explanation. "
            + "Use the required schema exactly."
        )
        strict_result = self._run_completion(strict_prompt)
        parsed = self._parse_json(strict_result)
        if parsed is not None:
            return parsed
        return fallback

    def _run_completion(self, prompt: str) -> str:
        try:
            response = self.llm.create_completion(
                prompt=prompt,
                temperature=self.planner_config["temperature"],
                max_tokens=self.planner_config["max_tokens"],
            )
        except Exception:
            return ""
        choices = response.get("choices", [])
        if not choices:
            return ""
        return str(choices[0].get("text", "")).strip()

    @staticmethod
    def _parse_json(payload: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(payload)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        parsed.setdefault("warning", None)
        parsed.setdefault("steps", [])
        parsed.setdefault("task", "UNKNOWN")
        parsed.setdefault("confidence", 0.0)
        return parsed

    @staticmethod
    def _fallback_plan(warning: str) -> dict[str, Any]:
        return {
            "task": "ABORT",
            "confidence": 0.0,
            "steps": [{"action": "rtl", "device": "fc", "params": {}}],
            "warning": warning,
        }
