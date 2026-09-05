#!/usr/bin/env python
"""
Convert external datasets to golden format for SAC pipeline.

1. FinRpt → golden markdown with frontmatter (one file per report)
2. AlphaFin → SFT instruction pairs (research subset)
3. CFQA → evaluation format (QA pairs for golden regression)
"""

import json
import re
from pathlib import Path

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
EXT = ROOT / "benchmark" / "external_datasets"
OUT = ROOT / "benchmark" / "external_datasets" / "processed"


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


# ── 1. FinRpt → golden markdown ──────────────────────────────


def convert_finrpt():
    """Convert FinRpt JSONL to golden-style markdown files with frontmatter."""
    print("=" * 60)
    print("Converting FinRpt → golden markdown")
    print("=" * 60)

    src = EXT / "FinRpt" / "FinRpt.jsonl"
    out_dir = OUT / "finrpt_reports"
    ensure_dir(out_dir)

    TASK_MAP = {
        "news_anlyzer": "新闻分析",
        "income": "利润表分析",
        "balance": "资产负债表分析",
        "cash": "现金流量表分析",
        "finance_write": "财务综述",
        "news_write": "新闻综述",
        "report_write": "投资建议报告",
        "risk": "风险提示",
        "trend_write": "趋势分析",
    }

    count = 0
    with open(src, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            stock = rec["stock_code"]
            date = rec["date"]
            rid = rec["id"]

            # Build markdown content
            parts = []
            parts.append(f"## {stock} 研究报告\n")
            parts.append(f"**日期**: {date}\n")
            parts.append(f"**股票代码**: {stock}\n")

            for task_key, task_name in TASK_MAP.items():
                prompt_key = f"{task_key}_prompt"
                response_key = f"{task_key}_response"
                if prompt_key in rec and response_key in rec:
                    parts.append(f"\n### {task_name}\n")
                    # Extract just the data portion from prompt (skip boilerplate)
                    prompt = rec[prompt_key]
                    # Find the actual data after common prefixes
                    data_match = re.search(r"(报告日期|日期)[:：]\s*\d{4}", prompt)
                    if data_match:
                        parts.append(f"**输入数据**:\n```\n{prompt[data_match.start() :]}\n```\n")
                    else:
                        parts.append(f"**输入数据**:\n```\n{prompt[-500:]}\n```\n")

                    output = rec[response_key]
                    # Try to parse as JSON for structured output
                    try:
                        parsed = json.loads(output)
                        if isinstance(parsed, dict):
                            for k, v in parsed.items():
                                if isinstance(v, str):
                                    parts.append(f"**{k}**: {v}\n")
                                elif isinstance(v, list):
                                    parts.append(f"**{k}**:\n")
                                    for item in v:
                                        if isinstance(item, dict):
                                            parts.append(f"- {json.dumps(item, ensure_ascii=False)}\n")
                                        else:
                                            parts.append(f"- {item}\n")
                                else:
                                    parts.append(f"**{k}**: {v}\n")
                        else:
                            parts.append(f"{output}\n")
                    except (json.JSONDecodeError, ValueError):
                        parts.append(f"{output}\n")

            content = "\n".join(parts)

            # Write with frontmatter
            safe_name = re.sub(r"[^\w\-.]", "_", rid)
            out_path = out_dir / f"{safe_name}.md"
            with open(out_path, "w", encoding="utf-8") as out_f:
                out_f.write(content)

            count += 1
            if count % 1000 == 0:
                print(f"  ... {count} reports converted")

    print(f"  Total: {count} reports → {out_dir}")
    return count


# ── 2. AlphaFin → SFT instruction pairs ─────────────────────


def convert_alphafin():
    """Extract research report subset from AlphaFin as SFT data."""
    print("\n" + "=" * 60)
    print("Converting AlphaFin → SFT instruction pairs")
    print("=" * 60)

    base = EXT / "AlphaFin"
    out_dir = OUT / "alphafin_sft"
    ensure_dir(out_dir)

    # Combine all training data
    all_records = []
    for fname, source in [
        ("train/research.json", "research"),
        ("train/fin_reports_raw.json", "fin_report"),
        ("train/stockqa.json", "stock_qa"),
        ("train/fin_news.json", "fin_news"),
    ]:
        p = base / fname
        if not p.exists():
            print(f"  SKIP {fname} (not found)")
            continue
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        for rec in data:
            rec["source"] = source
        all_records.extend(data)
        print(f"  {fname}: {len(data)} records")

    # Write combined SFT file
    out_path = out_dir / "alphafin_sft_train.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Also write eval subset (first 1000)
    eval_records = all_records[:1000]
    eval_path = out_dir / "alphafin_sft_eval.jsonl"
    with open(eval_path, "w", encoding="utf-8") as f:
        for rec in eval_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"  Total SFT: {len(all_records)} records → {out_path}")
    print(f"  Eval subset: {len(eval_records)} records → {eval_path}")
    return len(all_records)


# ── 3. CFQA → evaluation format ─────────────────────────────


def convert_cfqa():
    """Convert CFQA to evaluation format for golden regression."""
    print("\n" + "=" * 60)
    print("Converting CFQA → evaluation format")
    print("=" * 60)

    base = EXT / "CFQA" / "CFQA-main" / "dataset" / "split_by_company"
    out_dir = OUT / "cfqa_eval"
    ensure_dir(out_dir)

    # Read all splits
    all_qa = []
    for split_file in ["split_by_company_train.json", "split_by_company_dev.json", "split_by_company_test.json"]:
        p = base / split_file
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        for rec in data:
            rec["split"] = split_file.replace("split_by_company_", "").replace(".json", "")
        all_qa.extend(data)
        print(f"  {split_file}: {len(data)} QA pairs")

    # Map Chinese field names (from JSON encoding) to standard names
    # The fields are: 股票代码, 公司, 问题, 答案, 答案证据, id
    # But due to encoding they appear garbled - we need to detect them
    if all_qa:
        sample = all_qa[0]
        keys = list(sample.keys())
        print(f"  Fields: {keys}")

    # Write as JSONL for easy evaluation
    out_path = out_dir / "cfqa_eval.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in all_qa:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Stats
    splits = {}
    for rec in all_qa:
        s = rec.get("split", "unknown")
        splits[s] = splits.get(s, 0) + 1
    print(f"  Split counts: {splits}")
    print(f"  Total: {len(all_qa)} QA pairs → {out_path}")
    return len(all_qa)


# ── 4. Summary ───────────────────────────────────────────────


def main():
    ensure_dir(OUT)

    finrpt_count = convert_finrpt()
    alphafin_count = convert_alphafin()
    cfqa_count = convert_cfqa()

    print("\n" + "=" * 60)
    print("CONVERSION SUMMARY")
    print("=" * 60)
    print(f"  FinRpt → {finrpt_count} golden markdown reports")
    print(f"  AlphaFin → {alphafin_count} SFT instruction pairs")
    print(f"  CFQA → {cfqa_count} evaluation QA pairs")
    print(f"\n  Output: {OUT}")


if __name__ == "__main__":
    main()
