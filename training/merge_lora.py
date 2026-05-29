"""Merge a LoRA adapter into its base model before GGUF conversion."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge a DronePy LoRA adapter into a base model")
    parser.add_argument("--base-model", required=True, help="Base Hugging Face model path or id")
    parser.add_argument("--adapter-dir", required=True, help="Directory containing the saved LoRA adapter")
    parser.add_argument("--output-dir", required=True, help="Directory for the merged full model")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Missing merge dependencies. Install transformers and peft.") from exc

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_model = AutoModelForCausalLM.from_pretrained(args.base_model)
    merged = PeftModel.from_pretrained(base_model, args.adapter_dir)
    merged = merged.merge_and_unload()
    tokenizer = AutoTokenizer.from_pretrained(args.adapter_dir, use_fast=True)

    merged.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))


if __name__ == "__main__":
    main()

