# DronePy

DronePy is a starter codebase for a lightweight onboard drone runtime that:

- detects connected devices
- probes the attached flight controller
- builds a normalized capability profile
- feeds those features into a learned planner
- executes approved actions behind a safety boundary

The project intentionally keeps mission planning model-facing. The deterministic
parts are limited to hardware/protocol discovery, capability observation, and
safety overrides.

## Architecture

`device_inventory`

- hardware discovery providers
- normalized `DetectedDevice` records

`fc_probe`

- protocol-aware flight-controller probing
- controller family identification
- capability evidence extraction

`profile_store`

- persists controller snapshots and action outcomes
- lets the system accumulate observed capabilities over time

`planner`

- learned-planner interface
- structured feature payload for local or external models

`executor`

- action execution registry
- dry-run friendly by default

`safety`

- hard-stop guardrails for battery, link health, and missing capabilities

`runtime`

- end-to-end orchestration pipeline

## Quick Start

```bash
python -m dronepy "track a target and stream video"
```

The default CLI uses a null planner, so it performs discovery and safety
preparation but will not generate a mission until you inject a planner model.

## Training

The repo now includes a `training/` folder with:

- planner dataset schema
- example JSONL mission data
- LoRA fine-tuning script
- LoRA merge script
- GGUF export instructions aligned to DronePy's planner prompt format

Start with [training/README.md](D:/CityGrid/my-project/DronePy/training/README.md).

## Next Steps

1. Plug in a real learned planner that emits `MissionPlan`.
2. Add MAVLink/DroneCAN adapters with live protocol probing.
3. Feed execution outcomes back into `ProfileStore` for capability learning.
4. Add platform-specific providers for Raspberry Pi GPIO, CSI cameras, and I2C.
