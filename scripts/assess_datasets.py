#!/usr/bin/env python
"""Quality assessment of downloaded external datasets."""

import json
from pathlib import Path

BASE = Path(r"D:\Claude\projects\2hao-analyst\benchmark\external_datasets")


def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


# 1. FinRpt
section("1. FinRpt (AAAI 2026)")
p = BASE / "FinRpt/FinRpt.jsonl"
with open(p, encoding="utf-8") as f:
    lines = [json.loads(l) for l in f.readlines()[:5]]
codes = [r["stock_code"] for r in lines[:3]]
print("  Total: 6825 reports, 390 MB")
print(f"  Fields: {list(lines[0].keys())}")
print(f"  Sample codes: {codes}")
print("  9 tasks: news_anlyzer, income, balance, cash, finance_write, news_write, report_write, risk, trend_write")
print("  Format: prompt/response pairs per task")
print("  Quality: HIGH - structured input (financial data + news) -> structured output (analysis/report)")

# 2. AlphaFin
section("2. AlphaFin")
base = BASE / "AlphaFin"
for fname, desc in [
    ("train/research.json", "research reports"),
    ("train/fin_reports_raw.json", "fin reports raw"),
    ("train/stockqa.json", "stock QA"),
]:
    with open(base / fname, encoding="utf-8") as fh:
        data = json.load(fh)
    ins = data[0]["instruction"][:80]
    out = data[0]["output"][:80]
    print(f"  {desc}: {len(data)} records")
    print(f"    sample instruction: {ins}...")
    print(f"    sample output: {out}...")
print("  Format: instruction-input-output triplets")
print("  Quality: MEDIUM-HIGH - SFT-ready, diverse financial tasks")

# 3. CFQA
section("3. CFQA (Annual Report QA)")
base = BASE / "CFQA/CFQA-main/dataset/split_by_company"
with open(base / "split_by_company_train.json", encoding="utf-8") as fh:
    data = json.load(fh)
print(f"  Train: {len(data)} QA pairs")
print(f"  Fields: {list(data[0].keys())}")
rec = data[0]
for k in rec:
    v = rec[k]
    if isinstance(v, str):
        print(f"    {k}: {v[:80]}")
    else:
        print(f"    {k}: {v}")
print("  Quality: MEDIUM - annual report based QA, useful for evaluation")

# 4. DISC-FinLLM (demo only)
section("4. DISC-FinLLM (demo from GitHub)")
base = BASE / "DISC-FinLLM/DISC-FinLLM-main/data"
total = 0
for f in base.glob("*.json"):
    with open(f, encoding="utf-8") as fh:
        data = json.load(fh)
    total += len(data)
    print(f"  {f.name}: {len(data)} records")
print(f"  Total: {total} records (demo only, full 250K gated)")
print("  Quality: HIGH format, but too few samples")

# 5. SMPRR
section("5. SMPRR (东方财富研报+股价)")
base = BASE / "SMPRR/SMPRR-main"
prices = list((base / "prices").glob("*.csv"))
print(f"  Stock prices: {len(prices)} stocks")
report_xls = base / "reports/Pre/Data_2009.xls"
report_csv = base / "reports/Finished/Data_2009_Label.csv"
print(f"  Research reports: {report_xls.stat().st_size / 1e6:.1f} MB (XLS)")
print(f"  Labeled data: {report_csv.stat().st_size / 1e6:.1f} MB (CSV)")
print("  Scope: 2009 only, limited but paired with stock prices")
print("  Quality: LOW-MEDIUM - single year, small scale")

# Summary
section("SUMMARY - Usability for 2hao-analyst")
print("""
  Dataset        Size      Records   SFT-Ready  Relevance  Notes
  ─────────────────────────────────────────────────────────────
  FinRpt         390 MB    6,825     Yes        ★★★★★     Best fit: structured research reports
  AlphaFin       435 MB    85K+      Yes        ★★★★      Diverse financial NLP tasks
  CFQA           10 MB     10,311    Yes        ★★★       Annual report QA pairs
  DISC-FinLLM    1 MB      400       Yes        ★★        Demo only (full gated)
  SMPRR          12 MB     ~80 CSVs  No         ★★        2009 only, research+price pairs
""")
