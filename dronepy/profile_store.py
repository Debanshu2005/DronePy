from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import FlightControllerProfile


class ProfileStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(".dronepy")
        self.root.mkdir(parents=True, exist_ok=True)

    def profile_path(self, controller_id: str) -> Path:
        safe_id = controller_id.replace("\\", "_").replace("/", "_").replace(":", "_")
        return self.root / f"{safe_id}.json"

    def load(self, controller_id: str) -> dict[str, Any]:
        path = self.profile_path(controller_id)
        if not path.exists():
            return {"controller_id": controller_id, "history": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_profile(self, profile: FlightControllerProfile) -> Path:
        path = self.profile_path(profile.controller_id)
        payload = self.load(profile.controller_id)
        payload["latest_profile"] = {
            "family": profile.family,
            "transport": profile.transport,
            "firmware_version": profile.firmware_version,
            "capabilities": profile.capabilities,
            "modes": profile.modes,
            "telemetry_topics": profile.telemetry_topics,
            "limits": profile.limits,
            "confidence": profile.confidence,
            "metadata": profile.metadata,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def record_outcome(self, controller_id: str, outcome: dict[str, Any]) -> None:
        payload = self.load(controller_id)
        payload.setdefault("history", []).append(outcome)
        path = self.profile_path(controller_id)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

