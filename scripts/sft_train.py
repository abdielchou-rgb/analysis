#!/usr/bin/env python
"""
SFT fine-tuning script for Qwen2.5-7B using LoRA/QLoRA.

Usage:
    python scripts/sft_train.py --epochs 3 --batch_size 4 --lora_r 16

Requirements:
    pip install torch transformers peft datasets accelerate bitsandbytes
"""

import argparse
import json
from pathlib import Path

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
SFT_DATA = ROOT / "benchmark" / "sft_training"
OUTPUT = ROOT / "models" / "sft_qwen2.5_7b"
OUTPUT.mkdir(parents=True, exist_ok=True)


def load_data(split: str):
    """Load SFT data from JSONL."""
    path = SFT_DATA / f"sft_{split}.jsonl"
    data = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            data.append(
                {
                    "instruction": rec["instruction"],
                    "input": rec.get("input", ""),
                    "output": rec["output"],
                }
            )
    return data


def format_prompt(sample: dict) -> str:
    """Format sample into Qwen2.5 chat template."""
    instruction = sample["instruction"]
    inp = sample["input"]
    output = sample["output"]

    if inp:
        user_msg = f"{instruction}\n\n{inp}"
    else:
        user_msg = instruction

    return {
        "messages": [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": output},
        ]
    }


def setup_model(model_name: str = "Qwen/Qwen2.5-7B-Instruct", use_qlora: bool = True):
    """Setup model with LoRA/QLoRA configuration."""
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    # Quantization config for QLoRA
    if use_qlora:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype="float16",
            bnb_4bit_use_double_quant=True,
        )
    else:
        bnb_config = None

    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
        padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Prepare for k-bit training
    if use_qlora:
        model = prepare_model_for_kbit_training(model)

    # LoRA config
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    return model, tokenizer


def train(args):
    """Main training loop."""
    from datasets import Dataset
    from transformers import DataCollatorForSeq2Seq, Trainer, TrainingArguments

    print("Loading data...")
    train_data = load_data("train")
    eval_data = load_data("eval")

    # Format data
    train_dataset = Dataset.from_list([format_prompt(s) for s in train_data[: args.max_samples]])
    eval_dataset = Dataset.from_list([format_prompt(s) for s in eval_data[: args.max_eval_samples]])

    print(f"Train: {len(train_dataset)}, Eval: {len(eval_dataset)}")

    # Setup model
    print("Loading model...")
    model, tokenizer = setup_model(
        model_name=args.model,
        use_qlora=args.qlora,
    )

    # Tokenize
    def tokenize(examples):
        texts = [tokenizer.apply_chat_template(msgs, tokenize=False) for msgs in examples["messages"]]
        tokenized = tokenizer(
            texts,
            truncation=True,
            max_length=args.max_length,
            padding="max_length",
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    train_dataset = train_dataset.map(tokenize, batched=True, remove_columns=["messages"])
    eval_dataset = eval_dataset.map(tokenize, batched=True, remove_columns=["messages"])

    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(OUTPUT),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        weight_decay=0.01,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=500,
        save_strategy="steps",
        save_steps=500,
        save_total_limit=3,
        fp16=not args.qlora,
        bf16=False,
        dataloader_num_workers=4,
        report_to="none",
        remove_unused_columns=False,
    )

    # Data collator
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        max_length=args.max_length,
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
    )

    # Train
    print("Starting training...")
    trainer.train()

    # Save
    print("Saving model...")
    model.save_pretrained(str(OUTPUT / "lora_adapter"))
    tokenizer.save_pretrained(str(OUTPUT / "tokenizer"))

    print(f"\nDone! Model saved to {OUTPUT}")


def main():
    parser = argparse.ArgumentParser(description="SFT fine-tuning for Qwen2.5-7B")
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct", help="Base model")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--grad_accum", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--max_length", type=int, default=2048)
    parser.add_argument("--qlora", action="store_true", default=True)
    parser.add_argument("--no_qlora", dest="qlora", action="store_false")
    parser.add_argument("--max_samples", type=int, default=50000)
    parser.add_argument("--max_eval_samples", type=int, default=5000)
    args = parser.parse_args()

    train(args)


if __name__ == "__main__":
    main()
