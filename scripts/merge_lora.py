#!/usr/bin/env python
"""Merge LoRA adapter into base model and save."""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

LORA_PATH = "D:/Claude/projects/2hao-analyst/benchmark/sft_training/model_output/lora_adapter"
MERGED_PATH = "D:/Claude/projects/2hao-analyst/benchmark/sft_training/merged_model"

print("Loading base model...")
base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-7B-Instruct", torch_dtype=torch.float32, trust_remote_code=True
)

print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(base, LORA_PATH)

print("Merging LoRA into base model...")
model = model.merge_and_unload()

print("Saving merged model...")
model.save_pretrained(MERGED_PATH)

print("Saving tokenizer...")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
tokenizer.save_pretrained(MERGED_PATH)

print("Done! Merged model saved to:", MERGED_PATH)
