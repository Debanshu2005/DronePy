from __future__ import annotations

import argparse
import json

from .planner.interfaces import NullPlanner
from .runtime import DroneRuntime
from .schemas import MissionRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="DronePy runtime scaffold")
    parser.add_argument("request", nargs="?", help="Mission request text")
    parser.add_argument("--config", default="config.json", help="Path to the DronePy config file")
    parser.add_argument("--dry-run", action="store_true", help="Plan and safety-check without execution")
    args = parser.parse_args()

    runtime = DroneRuntime(planner=NullPlanner(), config_path=args.config)
    if args.request:
        result = runtime.run_instruction(args.request, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    while True:
        try:
            instruction = input("dronepy> ").strip()
        except EOFError:
            break
        if not instruction:
            continue
        result = runtime.run_instruction(instruction, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
