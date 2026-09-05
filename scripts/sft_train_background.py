#!/usr/bin/env python
"""SFT training script for 2hao-analyst (QLoRA on Qwen2.5-7B)."""

import argparse
import json
from pathlib import Path

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
TRAIN_DATA = ROOT / "benchmark" / "sft_training" / "sft_train.jsonl"
EVAL_DATA = ROOT / "benchmark" / "sft_training" / "sft_eval.jsonl"
OUTPUT_DIR = ROOT / "benchmark" / "sft_training" / "model_output"


def main():
    parser = argparse.ArgumentParser(description="SFT Training for 2hao-analyst")
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    parser.add_argument("--batch_size", type=int, default=4, help="Batch size")
    parser.add_argument("--learning_rate", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--qlora", action="store_true", help="Use QLoRA (4-bit quantization)")
    parser.add_argument("--lora_rank", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora_alpha", type=int, default=32, help="LoRA alpha")
    parser.add_argument("--max_length", type=int, default=2048, help="Max sequence length")
    parser.add_argument("--output_dir", type=str, default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    print("=" * 60)
    print("2hao-analyst SFT Training")
    print("=" * 60)
    print("Config:", vars(args))

    # Check data
    if not TRAIN_DATA.exists():
        print("ERROR: Training data not found:", TRAIN_DATA)
        return

    if not EVAL_DATA.exists():
        print("ERROR: Eval data not found:", EVAL_DATA)
        return

    # Count records
    with open(TRAIN_DATA, "r", encoding="utf-8") as f:
        train_count = sum(1 for _ in f)
    with open(EVAL_DATA, "r", encoding="utf-8") as f:
        eval_count = sum(1 for _ in f)

    print("Training records:", train_count)
    print("Eval records:", eval_count)

    # Check GPU
    try:
        import torch

        if torch.cuda.is_available():
            print("GPU:", torch.cuda.get_device_name(0))
            print("VRAM:", torch.cuda.get_device_properties(0).total_mem / 1024**3, "GB")
        else:
            print("WARNING: No GPU detected, training will be slow on CPU")
    except ImportError:
        print("WARNING: torch not installed")

    # Check dependencies
    try:
        import peft  # noqa: F401
        import transformers  # noqa: F401

        print("Dependencies OK")
    except ImportError as e:
        print("ERROR: Missing dependency:", e)
        print("Install with: pip install transformers peft accelerate bitsandbytes")
        return

    print("\nTraining configuration:")
    print("  Base model: Qwen2.5-7B-Instruct")
    print("  Method: %s" % ("QLoRA" if args.qlora else "LoRA"))
    print("  LoRA rank: %d" % args.lora_rank)
    print("  LoRA alpha: %d" % args.lora_alpha)
    print("  Epochs: %d" % args.epochs)
    print("  Batch size: %d" % args.batch_size)
    print("  Learning rate: %e" % args.learning_rate)
    print("  Max length: %d" % args.max_length)

    print("\nOutput directory:", args.output_dir)
    print("\nTo run training, execute:")
    print("  python scripts/sft_train.py --qlora --epochs 3")

    # Save config
    config = {
        "base_model": "Qwen/Qwen2.5-7B-Instruct",
        "method": "qlora" if args.qlora else "lora",
        "lora_rank": args.lora_rank,
        "lora_alpha": args.lora_alpha,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "max_length": args.max_length,
        "train_data": str(TRAIN_DATA),
        "eval_data": str(EVAL_DATA),
        "output_dir": args.output_dir,
    }

    config_path = Path(args.output_dir) / "training_config.json"
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print("\nConfig saved:", config_path)


if __name__ == "__main__":
    main()
