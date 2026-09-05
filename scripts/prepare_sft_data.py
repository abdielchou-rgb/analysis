#!/usr/bin/env python
"""
Prepare SFT training data from FinRpt + AlphaFin.

Output format: instruction-input-output triplets for LoRA/QLoRA fine-tuning.
Target model: Qwen2.5-7B (Chinese-optimized, 24GB VRAM sufficient)
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
FINRPT = ROOT / "benchmark" / "external_datasets" / "FinRpt" / "FinRpt.jsonl"
ALPHAFIN_DIR = ROOT / "benchmark" / "external_datasets" / "AlphaFin"
OUT = ROOT / "benchmark" / "sft_training"
OUT.mkdir(parents=True, exist_ok=True)

# ── FinRpt → SFT ─────────────────────────────────────────────

FINRPT_TASKS = {
    "income": {
        "instruction": "基于以下财务数据，撰写专业的利润表分析。要求：1)每段开头有判断词；2)使用因果连接词；3)关键数据有来源标注；4)末尾给出投资含义。",
        "section": "利润表分析",
    },
    "balance": {
        "instruction": "基于以下财务数据，撰写专业的资产负债表分析。要求：1)分析资产结构和负债水平；2)关注偿债能力指标；3)识别风险信号；4)给出投资含义。",
        "section": "资产负债表分析",
    },
    "cash": {
        "instruction": "基于以下财务数据，撰写专业的现金流量表分析。要求：1)分析三大现金流；2)关注自由现金流；3)评估现金流质量；4)给出投资含义。",
        "section": "现金流量表分析",
    },
    "finance_write": {
        "instruction": "基于以下三表数据，撰写综合财务分析报告。要求：1)综合三表关键发现；2)评估财务健康度；3)识别核心风险；4)给出投资含义。",
        "section": "财务综述",
    },
    "report_write": {
        "instruction": "基于以下数据，撰写投资建议报告。要求：1)给出明确投资评级；2)给出目标价及估值方法；3)列出核心催化剂；4)说明投资逻辑。",
        "section": "投资建议报告",
    },
    "trend_write": {
        "instruction": "基于以下数据，撰写股价趋势分析。要求：1)分析当前股价位置；2)识别催化剂和风险；3)给出未来展望；4)说明与大盘的相对表现。",
        "section": "趋势分析",
    },
    "risk": {
        "instruction": "基于以下数据，识别并分析核心风险因素。要求：1)识别3-5个核心风险；2)按影响程度排序；3)说明触发条件和潜在影响；4)给出风险缓释建议。",
        "section": "风险提示",
    },
    "news_write": {
        "instruction": "基于以下新闻数据，撰写新闻综述。要求：1)识别最重要的3-5条新闻；2)分析每条新闻的影响；3)判断市场预期差；4)给出投资含义。",
        "section": "新闻综述",
    },
    "news_anlyzer": {
        "instruction": "基于以下新闻事件，撰写深度分析。要求：1)分析事件背景和原因；2)评估短期和长期影响；3)识别市场预期差；4)给出投资含义。",
        "section": "新闻分析",
    },
}


def convert_finrpt_to_sft():
    """Convert FinRpt JSONL to SFT instruction-input-output format."""
    print("=" * 60)
    print("Converting FinRpt → SFT format")
    print("=" * 60)

    records = []
    with open(FINRPT, encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    sft_data = []
    for rec in records:
        stock = rec["stock_code"]
        date = rec["date"]

        for task_key, meta in FINRPT_TASKS.items():
            prompt = rec.get(f"{task_key}_prompt", "")
            response = rec.get(f"{task_key}_response", "")
            if not response.strip():
                continue

            # Extract input data from prompt (skip boilerplate)
            input_data = extract_input_from_prompt(prompt)

            # Build SFT record
            sft_record = {
                "instruction": meta["instruction"],
                "input": f"公司：{stock}\n日期：{date}\n\n{input_data}",
                "output": format_output(response, task_key),
                "metadata": {
                    "source": "finrpt",
                    "stock_code": stock,
                    "date": date,
                    "task": task_key,
                    "section": meta["section"],
                },
            }
            sft_data.append(sft_record)

    print(f"  FinRpt: {len(sft_data)} SFT records from {len(records)} reports")
    return sft_data


def extract_input_from_prompt(prompt: str) -> str:
    """Extract core data from FinRpt prompt, removing boilerplate."""
    import re

    # Find data after common prefixes
    patterns = [
        r"(报告日期|日期)[:：]\s*\d{4}",
        r"(公司概况|公司名称)[:：]",
    ]
    for pat in patterns:
        m = re.search(pat, prompt)
        if m:
            return prompt[m.start() :]
    # Fallback: return last 60%
    start = int(len(prompt) * 0.4)
    return prompt[start:]


def format_output(response: str, task_key: str) -> str:
    """Format output for SFT training."""
    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            parts = []
            for k, v in parsed.items():
                if isinstance(v, str):
                    parts.append(f"{k}：{v}")
                elif isinstance(v, list):
                    parts.append(f"{k}：")
                    for item in v:
                        if isinstance(item, dict):
                            parts.append(f"  - {json.dumps(item, ensure_ascii=False)}")
                        else:
                            parts.append(f"  - {item}")
                else:
                    parts.append(f"{k}：{v}")
            return "\n".join(parts)
    except (json.JSONDecodeError, ValueError):
        pass
    return response


# ── AlphaFin → SFT ───────────────────────────────────────────


def convert_alphafin_to_sft():
    """Convert AlphaFin JSON to SFT format."""
    print("\n" + "=" * 60)
    print("Converting AlphaFin → SFT format")
    print("=" * 60)

    sft_data = []
    for fname, source in [
        ("train/research.json", "research"),
        ("train/fin_reports_raw.json", "fin_report"),
        ("train/stockqa.json", "stock_qa"),
        ("train/fin_news.json", "fin_news"),
    ]:
        p = ALPHAFIN_DIR / fname
        if not p.exists():
            print(f"  SKIP {fname} (not found)")
            continue
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        for rec in data:
            sft_record = {
                "instruction": rec.get("instruction", ""),
                "input": rec.get("input", ""),
                "output": rec.get("output", ""),
                "metadata": {
                    "source": f"alphafin_{source}",
                    "task": source,
                },
            }
            sft_data.append(sft_record)
        print(f"  {fname}: {len(data)} records")

    print(f"  AlphaFin total: {len(sft_data)} SFT records")
    return sft_data


# ── Combine & Deduplicate ─────────────────────────────────────


def combine_and_deduplicate(finrpt_data: list, alphafin_data: list) -> list:
    """Combine and deduplicate SFT data."""
    print("\n" + "=" * 60)
    print("Combining and deduplicating")
    print("=" * 60)

    all_data = finrpt_data + alphafin_data

    # Deduplicate by content hash
    seen = set()
    unique = []
    for rec in all_data:
        content = f"{rec['instruction']}|{rec['input']}|{rec['output']}"
        h = hashlib.md5(content.encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(rec)

    print(f"  Total: {len(all_data)} → Unique: {len(unique)}")
    print(f"  Dedup removed: {len(all_data) - len(unique)}")

    return unique


# ── Quality Filter ────────────────────────────────────────────


def quality_filter(data: list) -> list:
    """Filter low-quality SFT records."""
    print("\n" + "=" * 60)
    print("Quality filtering")
    print("=" * 60)

    filtered = []
    reasons = Counter()

    for rec in data:
        # Skip empty outputs
        if not rec["output"].strip():
            reasons["empty_output"] += 1
            continue

        # Skip too-short outputs
        if len(rec["output"]) < 20:
            reasons["too_short"] += 1
            continue

        # Skip too-long outputs (likely noise)
        if len(rec["output"]) > 2000:
            reasons["too_long"] += 1
            continue

        # Skip empty instructions
        if not rec["instruction"].strip():
            reasons["empty_instruction"] += 1
            continue

        filtered.append(rec)

    print(f"  Before: {len(data)} → After: {len(filtered)}")
    print(f"  Removed: {len(data) - len(filtered)}")
    for reason, count in reasons.most_common():
        print(f"    {reason}: {count}")

    return filtered


# ── Split & Save ──────────────────────────────────────────────


def split_and_save(data: list):
    """Split into train/eval and save."""
    print("\n" + "=" * 60)
    print("Splitting and saving")
    print("=" * 60)

    # Shuffle
    import random

    random.seed(42)
    random.shuffle(data)

    # Split: 90% train, 10% eval
    split_idx = int(len(data) * 0.9)
    train = data[:split_idx]
    eval_ = data[split_idx:]

    # Save
    for split_name, split_data in [("train", train), ("eval", eval_)]:
        out_path = OUT / f"sft_{split_name}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for rec in split_data:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  {split_name}: {len(split_data)} records → {out_path}")

    # Save metadata
    meta = {
        "total": len(data),
        "train": len(train),
        "eval": len(eval_),
        "sources": Counter(rec["metadata"]["source"] for rec in data),
        "tasks": Counter(rec["metadata"].get("task", "unknown") for rec in data),
    }
    with open(OUT / "sft_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"  Metadata → {OUT / 'sft_metadata.json'}")


# ── Main ──────────────────────────────────────────────────────


def main():
    finrpt_data = convert_finrpt_to_sft()
    alphafin_data = convert_alphafin_to_sft()
    combined = combine_and_deduplicate(finrpt_data, alphafin_data)
    filtered = quality_filter(combined)
    split_and_save(filtered)

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
