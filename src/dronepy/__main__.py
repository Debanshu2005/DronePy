from __future__ import annotations

import argparse

from .planner.interfaces import NullPlanner
from .runtime import DroneRuntime
from .schemas import MissionRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="DronePy runtime scaffold")
    parser.add_argument("request", help="Mission request text")
    args = parser.parse_args()

    runtime = DroneRuntime(planner=NullPlanner())
    snapshot = runtime.inspect()
    print(snapshot.to_json())

    result = runtime.plan(MissionRequest(text=args.request), snapshot=snapshot)
    print(result.to_json())


if __name__ == "__main__":
    main()

