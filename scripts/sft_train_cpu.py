#!/usr/bin/env python
"""SFT Training for 2hao-analyst (CPU compatible)."""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
TRAIN_DATA = ROOT / "benchmark" / "sft_training" / "sft_train.jsonl"
EVAL_DATA = ROOT / "benchmark" / "sft_training" / "sft_eval.jsonl"
OUTPUT_DIR = ROOT / "benchmark" / "sft_training" / "model_output"


def load_data(path, max_samples=1000):
    """Load JSONL data."""
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_samples > 0 and i >= max_samples:
                break
            data.append(json.loads(line))
    return data


def main():
    print("=" * 60)
    print("2hao-analyst SFT Training (CPU Mode)")
    print("=" * 60)
    print("Start:", datetime.now().isoformat())

    # Use hf-mirror for China
    import os

    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    print("HF_ENDPOINT:", os.environ.get("HF_ENDPOINT"))

    # Check dependencies
    try:
        import torch  # noqa: F401
        from peft import LoraConfig, TaskType, get_peft_model  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments  # noqa: F401

        print("Dependencies OK")
    except ImportError as e:
        print("ERROR: Missing dependency:", e)
        sys.exit(1)

    # Config
    config = {
        "base_model": "Qwen/Qwen2.5-7B-Instruct",
        "method": "lora",
        "lora_rank": 16,
        "lora_alpha": 32,
        "epochs": 3,
        "batch_size": 1,
        "gradient_accumulation": 8,
        "learning_rate": 2e-4,
        "max_length": 512,
        "max_samples": 10000,
    }

    print("\nConfig:", json.dumps(config, indent=2))

    # Load data
    print("\nLoading training data...")
    train_data = load_data(TRAIN_DATA, config["max_samples"])
    eval_data = load_data(EVAL_DATA, 20)
    print("Train: %d samples" % len(train_data))
    print("Eval: %d samples" % len(eval_data))

    # Load model
    print("\nLoading model:", config["base_model"])
    try:
        tokenizer = AutoTokenizer.from_pretrained(config["base_model"], trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            config["base_model"],
            torch_dtype=torch.float32,  # Use float32 for CPU
            trust_remote_code=True,
        )
        print("Model loaded")
    except Exception as e:
        print("ERROR loading model:", e)
        print("\nNote: First run will download the model (~15GB)")
        sys.exit(1)

    # Apply LoRA
    print("\nApplying LoRA...")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config["lora_rank"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=0.1,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Prepare data
    def preprocess(examples):
        texts = []
        for ex in examples:
            prompt = ex.get("instruction", "")
            response = ex.get("output", "")
            text = "User: %s\nAssistant: %s" % (prompt, response)
            texts.append(text)

        encodings = tokenizer(
            texts, truncation=True, padding="max_length", max_length=config["max_length"], return_tensors="pt"
        )
        encodings["labels"] = encodings["input_ids"].clone()
        return encodings

    print("\nPreprocessing data...")
    train_dataset = preprocess(train_data)
    eval_dataset = preprocess(eval_data)

    # Training args
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=config["epochs"],
        per_device_train_batch_size=config["batch_size"],
        gradient_accumulation_steps=config["gradient_accumulation"],
        learning_rate=config["learning_rate"],
        fp16=False,  # No FP16 on CPU
        bf16=False,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        eval_strategy="steps",
        eval_steps=50,
        load_best_model_at_end=True,
        report_to="none",
    )

    # Custom dataset class
    class SimpleDataset(torch.utils.data.Dataset):
        def __init__(self, encodings):
            self.encodings = encodings

        def __len__(self):
            return len(self.encodings["input_ids"])

        def __getitem__(self, idx):
            return {k: v[idx] for k, v in self.encodings.items()}

    train_dataset = SimpleDataset(train_dataset)
    eval_dataset = SimpleDataset(eval_dataset)

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
    )

    # Train
    print("\nStarting training...")
    print("Estimated time: ~30-60 minutes (CPU)")
    trainer.train()

    # Save
    print("\nSaving model...")
    model.save_pretrained(str(OUTPUT_DIR / "lora_adapter"))
    tokenizer.save_pretrained(str(OUTPUT_DIR / "tokenizer"))

    print("\nTraining complete!")
    print("End:", datetime.now().isoformat())
    print("Output:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
