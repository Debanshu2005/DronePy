from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from dronepy.capability_profile import CapabilityProfile
from dronepy.planner.slm_planner import build_prompt as runtime_build_prompt
from dronepy.schemas import FCCapabilities


TRAINING_DIR = Path(__file__).resolve().parents[1] / "training"


def load_training_module():
    module_path = TRAINING_DIR / "planner_dataset.py"
    spec = importlib.util.spec_from_file_location("planner_dataset", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TrainingAssetsTests(unittest.TestCase):
    def test_example_dataset_validates(self) -> None:
        planner_dataset = load_training_module()
        examples = planner_dataset.load_jsonl(TRAINING_DIR / "examples" / "planner_examples.jsonl")
        self.assertGreaterEqual(len(examples), 3)

    def test_prompt_format_contains_runtime_sections(self) -> None:
        planner_dataset = load_training_module()
        examples = planner_dataset.load_jsonl(TRAINING_DIR / "examples" / "planner_examples.jsonl")
        prompt = planner_dataset.build_prompt(examples[0])
        self.assertIn("### Instruction:", prompt)
        self.assertIn("### Hardware:", prompt)
        self.assertIn("### Behavior Rules:", prompt)
        self.assertIn("### Recent Mission History:", prompt)
        self.assertIn("### Response:", prompt)

    def test_training_prompt_matches_runtime_prompt(self) -> None:
        planner_dataset = load_training_module()
        example = planner_dataset.load_jsonl(TRAINING_DIR / "examples" / "planner_examples.jsonl")[0]
        training_prompt = planner_dataset.build_prompt(example)

        profile = CapabilityProfile(
            sensors=example["hardware"]["sensors"],
            fc=FCCapabilities(
                controller_family=example["hardware"]["fc"]["controller_family"],
                armed=example["hardware"]["fc"]["armed"],
                battery_voltage=example["hardware"]["fc"]["battery_voltage"],
                reachable=True,
            ),
        )
        runtime_prompt = runtime_build_prompt(
            example["instruction"],
            profile,
            example["recent_missions"],
            example["behavior"],
        )
        self.assertEqual(training_prompt, runtime_prompt)

    def test_grouped_example_sets_validate_and_total_over_fifty(self) -> None:
        planner_dataset = load_training_module()
        grouped_paths = [
            TRAINING_DIR / "examples" / "normal_missions.jsonl",
            TRAINING_DIR / "examples" / "degraded_cases.jsonl",
            TRAINING_DIR / "examples" / "emergency_cases.jsonl",
        ]
        total = 0
        for path in grouped_paths:
            examples = planner_dataset.load_jsonl(path)
            self.assertGreater(len(examples), 0)
            total += len(examples)
        self.assertGreaterEqual(total, 50)


if __name__ == "__main__":
    unittest.main()
