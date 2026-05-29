from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


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


if __name__ == "__main__":
    unittest.main()
