from __future__ import annotations

from typing import Callable

from ..schemas import ExecutionReport, MissionPlan, SafetyDecision

ActionExecutor = Callable[[str], bool]


class ExecutionEngine:
    def __init__(self, handlers: dict[str, ActionExecutor] | None = None) -> None:
        self.handlers = handlers or {}

    def execute(self, plan: MissionPlan, safety: SafetyDecision) -> ExecutionReport:
        if not safety.approved:
            return ExecutionReport(plan=plan, safety=safety)

        executed: list[str] = []
        failed: list[str] = []
        for action in plan.actions:
            handler = self.handlers.get(action)
            if handler is None:
                failed.append(action)
                continue
            if handler(action):
                executed.append(action)
            else:
                failed.append(action)

        return ExecutionReport(
            plan=plan,
            safety=safety,
            executed_actions=executed,
            failed_actions=failed,
        )

