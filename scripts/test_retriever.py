#!/usr/bin/env python
"""Test exemplar retriever."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\Claude\projects\2hao-analyst\scripts")))
from exemplar_retriever import ExemplarRetriever

r = ExemplarRetriever()
stats = r.get_stats()
print("Stats:")
print(json.dumps(stats, indent=2, ensure_ascii=False))

# Test retrieval for each section
sections = ["利润表分析", "资产负债表分析", "现金流量表分析", "投资建议报告", "风险提示", "趋势分析"]
for section in sections:
    print(f"\n{'=' * 60}")
    print(f"Section: {section}")
    print(f"{'=' * 60}")
    exemplars = r.retrieve(section=section, n=3)
    for i, ex in enumerate(exemplars):
        print(f"\n  Exemplar {i + 1}: {ex['stock_code']} (quality={ex['quality_score']})")
        out = ex["output_raw"]
        # Try to parse JSON
        try:
            parsed = json.loads(out)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if isinstance(v, str):
                        print(f"    {k}: {v[:150]}")
                    else:
                        print(f"    {k}: {v}")
        except (json.JSONDecodeError, ValueError):
            print(f"    Output: {out[:200]}")
