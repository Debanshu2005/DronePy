# Training

This folder contains the pieces needed to train the offline planner used by
`dronepy.planner.slm_planner`.

The planner is trained as a structured text-to-JSON model:

- input: mission instruction + hardware context + behavior rules + recent missions
- output: JSON procedure matching DronePy's runtime schema

Files:

- `dataset_schema.json`: JSON Schema for planner training examples
- `planner_dataset.py`: validation and prompt-formatting helpers
- `examples/planner_examples.jsonl`: starter supervised dataset
- `finetune_lora.py`: LoRA fine-tuning entrypoint for a small base instruct model
- `merge_lora.py`: merge a LoRA adapter back into a Hugging Face model directory
- `export_gguf.md`: steps to export the merged model to GGUF for DronePy

Typical workflow:

1. Expand `examples/planner_examples.jsonl` into a real mission dataset.
2. Fine-tune with `python training/finetune_lora.py ...`.
3. Merge adapters with `python training/merge_lora.py ...`.
4. Convert and quantize to GGUF using `training/export_gguf.md`.
5. Place the final file at `models/drone_slm.gguf`.

Recommended starting point for an `8 GB RAM + GTX 1650` laptop:

- base model: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- `--batch-size 1`
- `--grad-accum 16`
- `--max-seq-length 512`
- `--fp16`
- `--gradient-checkpointing`

If your environment supports it, try `--load-in-8bit` before attempting 4-bit.
