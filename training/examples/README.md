# Example Datasets

`planner_examples.jsonl` is a starter supervised dataset for DronePy's planner.

It deliberately mixes:

- normal missions
- degraded-mode fallbacks
- emergency overrides
- different sensor combinations
- different FC families

Use it as a seed set, not a final production dataset.

Additional grouped datasets:

- `normal_missions.jsonl`
- `degraded_cases.jsonl`
- `emergency_cases.jsonl`

Together, the grouped sets contain more than 50 examples and are better suited
for a first meaningful fine-tuning run than the tiny starter file alone.

Good next additions:

- more partial-failure examples
- more no-GPS scenarios
- more mission-resume examples
- payload-specific missions for your real drone hardware
- logs converted from SITL or real flights
