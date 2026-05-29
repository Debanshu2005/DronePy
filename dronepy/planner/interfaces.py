from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from ..schemas import MissionPlan, PlannerFeatures


class LearnedPlanner(Protocol):
    def plan(self, features: PlannerFeatures) -> MissionPlan:
        """Generate a mission plan from learned features."""


class NullPlanner:
    """Placeholder planner until a learned model is wired in."""

    def plan(self, features: PlannerFeatures) -> MissionPlan:
        controller_family = features.controller.family if features.controller else "unknown"
        return MissionPlan(
            plan_id=str(uuid4()),
            intent="planner_unavailable",
            actions=[],
            confidence=0.0,
            metadata={
                "message": "No learned planner is configured yet.",
                "controller_family": controller_family,
                "request_text": features.request.text,
            },
        )

