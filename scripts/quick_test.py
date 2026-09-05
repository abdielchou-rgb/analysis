#!/usr/bin/env python
"""Quick test of exemplar retriever output."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\Claude\projects\2hao-analyst\scripts")))
from exemplar_retriever import ExemplarRetriever

r = ExemplarRetriever()
exemplars = r.retrieve(section="利润表分析", n=2)

for ex in exemplars:
    stock = ex["stock_code"]
    out = ex["output_raw"]
    print("Stock:", stock)
    print("Output length:", len(out))
    print("Output type:", type(out))
    print("First 300 chars:", repr(out[:300]))
    print()
