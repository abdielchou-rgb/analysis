#!/usr/bin/env python
"""Test LoRA model inference."""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"


def main():
    print("=" * 60)
    print("2hao-analyst LoRA Model Inference Test")
    print("=" * 60)

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))

    # Load base model with 4-bit quantization
    print("\nLoading base model...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )

    base_model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen2.5-7B-Instruct", quantization_config=bnb_config, device_map="auto", trust_remote_code=True
    )

    # Load LoRA adapter
    print("Loading LoRA adapter...")
    lora_path = r"D:\Claude\projects\2hao-analyst\benchmark\sft_training\model_output\lora_adapter"
    model = PeftModel.from_pretrained(base_model, lora_path)

    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")

    # Test prompts
    test_prompts = [
        "分析：贵州茅台 2025年业绩展望",
        "比较：比亚迪 vs 特斯拉 竞争优势",
        "评估：宁德时代 新能源电池市场地位",
    ]

    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n--- Test {i} ---")
        print(f"Prompt: {prompt}")

        inputs = tokenizer(f"User: {prompt}\nAssistant:", return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
            )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Extract only the assistant's response
        if "Assistant:" in response:
            response = response.split("Assistant:")[-1].strip()

        print(f"Response: {response[:500]}...")

    print("\n" + "=" * 60)
    print("Inference test completed!")


if __name__ == "__main__":
    main()
