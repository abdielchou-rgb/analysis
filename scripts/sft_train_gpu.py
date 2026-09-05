#!/usr/bin/env python
"""SFT Training with GPU QLoRA."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
TRAIN_DATA = ROOT / "benchmark" / "sft_training" / "sft_train.jsonl"
OUTPUT_DIR = ROOT / "benchmark" / "sft_training" / "model_output_gpu"


def load_data(path, max_samples=0):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_samples > 0 and i >= max_samples:
                break
            data.append(json.loads(line))
    return data


def main():
    print("=" * 60)
    print("2hao-analyst SFT Training (GPU QLoRA)")
    print("=" * 60)
    print("Start:", datetime.now().isoformat())

    import torch
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments

    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))
        print("Free memory:", torch.cuda.mem_get_info()[0] / 1024**3, "GB")

    config = {
        "base_model": "Qwen/Qwen2.5-7B-Instruct",
        "epochs": 3,
        "batch_size": 1,
        "gradient_accumulation": 8,
        "learning_rate": 2e-4,
        "max_length": 512,
        "max_samples": 10000,  # 10K samples for GPU training
        "lora_rank": 16,
        "lora_alpha": 32,
    }

    print("\nConfig:", json.dumps(config, indent=2))

    # Load data
    print("\nLoading training data...")
    train_data = load_data(TRAIN_DATA, config["max_samples"])
    print("Train:", len(train_data), "samples")

    # Load model with 4-bit quantization
    print("\nLoading model with QLoRA...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        config["base_model"], quantization_config=bnb_config, device_map="auto", trust_remote_code=True
    )
    model = prepare_model_for_kbit_training(model)

    tokenizer = AutoTokenizer.from_pretrained(config["base_model"])

    # Apply LoRA
    print("Applying LoRA...")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config["lora_rank"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=0.1,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Prepare dataset
    class SimpleDataset(torch.utils.data.Dataset):
        def __init__(self, data, tokenizer, max_length):
            self.data = data
            self.tokenizer = tokenizer
            self.max_length = max_length

        def __len__(self):
            return len(self.data)

        def __getitem__(self, idx):
            ex = self.data[idx]
            text = f"User: {ex.get('instruction', '')}\nAssistant: {ex.get('output', '')}"
            encodings = self.tokenizer(
                text, truncation=True, padding="max_length", max_length=self.max_length, return_tensors="pt"
            )
            encodings["labels"] = encodings["input_ids"].clone()
            return {k: v.squeeze() for k, v in encodings.items()}

    print("Preparing dataset...")
    train_dataset = SimpleDataset(train_data, tokenizer, config["max_length"])

    # Training args
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=config["epochs"],
        per_device_train_batch_size=config["batch_size"],
        gradient_accumulation_steps=config["gradient_accumulation"],
        learning_rate=config["learning_rate"],
        fp16=True,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        report_to="none",
        optim="paged_adamw_8bit",
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
    )

    # Train
    print("\nStarting GPU QLoRA training...")
    print("Estimated time: ~2-4 hours")
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
