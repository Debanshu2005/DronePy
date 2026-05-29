# GGUF Export

These steps assume you already trained a LoRA adapter with
`training/finetune_lora.py` and merged it with `training/merge_lora.py`.

The goal is to produce a GGUF file that works with
[`dronepy/planner/slm_planner.py`](D:/CityGrid/my-project/DronePy/dronepy/planner/slm_planner.py),
which expects a local planner model that answers with JSON matching DronePy's
procedure schema.

## 1. Train the adapter

Example:

```bash
python training/finetune_lora.py ^
  --dataset training/examples/planner_examples.jsonl ^
  --base-model TinyLlama/TinyLlama-1.1B-Chat-v1.0 ^
  --output-dir training/out/tinydrone_lora
```

## 2. Merge the adapter

```bash
python training/merge_lora.py ^
  --base-model TinyLlama/TinyLlama-1.1B-Chat-v1.0 ^
  --adapter-dir training/out/tinydrone_lora/adapter ^
  --output-dir training/out/tinydrone_merged
```

## 3. Convert to GGUF with llama.cpp

From your local `llama.cpp` checkout:

```bash
python convert_hf_to_gguf.py training/out/tinydrone_merged --outfile drone_slm-f16.gguf --outtype f16
```

## 4. Quantize for Raspberry Pi

`Q4_K_M` is a good starting point for a Pi 4B:

```bash
./llama-quantize drone_slm-f16.gguf drone_slm-q4_k_m.gguf Q4_K_M
```

## 5. Install into DronePy

Copy the quantized model into:

```text
models/drone_slm.gguf
```

Then keep `config.json` aligned:

```json
"planner": {
  "model_path": "models/drone_slm.gguf",
  "fallback": "abort",
  "temperature": 0.1,
  "max_tokens": 300
}
```

## 6. Validate planner behavior

After export, test the same prompt style used during training:

- instruction
- hardware summary
- behavior rules
- recent mission history
- JSON-only response

The model should reliably emit:

```json
{
  "task": "SURVEY",
  "confidence": 0.93,
  "steps": [
    {"action": "arm", "device": "fc", "params": {}}
  ],
  "warning": null
}
```

## Notes

- Keep the action vocabulary narrow during early training.
- Include degraded and emergency examples in the dataset.
- DronePy's safety layer still overrides unsafe plans after inference.

