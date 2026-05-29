"""Fine-tune a small planner model with LoRA on DronePy JSONL mission data."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from planner_dataset import format_supervised_text, load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LoRA fine-tuning for DronePy planner models")
    parser.add_argument("--dataset", required=True, help="Path to planner training JSONL")
    parser.add_argument("--base-model", required=True, help="Base Hugging Face causal LM")
    parser.add_argument("--output-dir", required=True, help="Directory for LoRA checkpoints")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--learning-rate", type=float, default=2e-4, help="LoRA learning rate")
    parser.add_argument("--batch-size", type=int, default=1, help="Per-device train batch size")
    parser.add_argument("--grad-accum", type=int, default=16, help="Gradient accumulation steps")
    parser.add_argument("--max-seq-length", type=int, default=512, help="Tokenizer truncation length")
    parser.add_argument("--fp16", action="store_true", help="Enable fp16 training when CUDA is available")
    parser.add_argument(
        "--gradient-checkpointing",
        action="store_true",
        help="Enable gradient checkpointing to reduce VRAM usage",
    )
    parser.add_argument("--load-in-8bit", action="store_true", help="Load the base model in 8-bit mode")
    parser.add_argument("--load-in-4bit", action="store_true", help="Load the base model in 4-bit mode")
    return parser.parse_args()


def build_model_kwargs(args: argparse.Namespace, torch_module: Any, transformers_module: Any) -> dict[str, Any]:
    """Build memory-aware model loading kwargs for small-GPU LoRA training."""
    kwargs: dict[str, Any] = {"low_cpu_mem_usage": True}
    if torch_module.cuda.is_available():
        kwargs["device_map"] = "auto"
    if args.load_in_4bit:
        kwargs["quantization_config"] = transformers_module.BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch_module.float16,
        )
    elif args.load_in_8bit:
        kwargs["quantization_config"] = transformers_module.BitsAndBytesConfig(load_in_8bit=True)
    return kwargs


def main() -> None:
    args = parse_args()
    try:
        from datasets import Dataset
        from peft import LoraConfig
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTConfig, SFTTrainer
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Missing training dependencies. Install datasets, transformers, peft, accelerate, trl, and torch."
        ) from exc

    examples = load_jsonl(args.dataset)
    if not examples:
        raise SystemExit("Dataset is empty.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = Dataset.from_list([{"text": format_supervised_text(example)} for example in examples])

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs = build_model_kwargs(args, torch, transformers)
    model = AutoModelForCausalLM.from_pretrained(args.base_model, **model_kwargs)
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        model.config.use_cache = False

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    training_args = SFTConfig(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        logging_steps=10,
        save_strategy="epoch",
        bf16=False,
        fp16=bool(args.fp16 and torch.cuda.is_available()),
        max_length=args.max_seq_length,
        dataset_text_field="text",
        report_to=[],
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
        args=training_args,
    )

    trainer.train()
    trainer.save_model(str(output_dir / "adapter"))
    tokenizer.save_pretrained(str(output_dir / "adapter"))

    summary_path = output_dir / "training_summary.txt"
    summary_path.write_text(
        "\n".join(
            [
                f"dataset={args.dataset}",
                f"base_model={args.base_model}",
                f"examples={len(examples)}",
                f"epochs={args.epochs}",
                f"learning_rate={args.learning_rate}",
                f"batch_size={args.batch_size}",
                f"grad_accum={args.grad_accum}",
                f"fp16={bool(args.fp16 and torch.cuda.is_available())}",
                f"gradient_checkpointing={args.gradient_checkpointing}",
                f"load_in_8bit={args.load_in_8bit}",
                f"load_in_4bit={args.load_in_4bit}",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
