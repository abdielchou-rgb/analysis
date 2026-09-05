#!/usr/bin/env python
"""Analyze FinRpt data structure and content quality."""

import json
from pathlib import Path

p = Path(r"D:\Claude\projects\2hao-analyst\benchmark\external_datasets\FinRpt\FinRpt.jsonl")
with open(p, encoding="utf-8") as f:
    records = [json.loads(line) for line in f.readlines()[:10]]

for i, r in enumerate(records):
    stock = r["stock_code"]
    date = r["date"]
    print(f"{'=' * 60}")
    print(f"Record {i}: {stock} @ {date}")
    print(f"{'=' * 60}")

    for task in ["report_write", "income", "risk", "trend_write", "finance_write"]:
        out_key = f"{task}_response"
        in_key = f"{task}_prompt"
        out = r.get(out_key, "")
        inp = r.get(in_key, "")
        print(f"\n--- {task} ---")
        print(f"Input length: {len(inp)} chars")
        print(f"Output length: {len(out)} chars")
        print(f"Output preview: {out[:300]}")
    print()
