# -*- coding: utf-8 -*-
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\2hao-analyst")
from pipeline.iron_gate import IronGate

p = r"D:\2hao-analyst\output\柯力传感深度分析报告_v5_20260804.md"
text = open(p, encoding="utf-8").read()
# 剥离 YAML front matter（管线内 report_text 不含该头）
if text.startswith("---"):
    parts = text.split("---", 2)
    if len(parts) == 3:
        text = parts[2]

gate = IronGate.from_text(text, report_type="listed_company", style="cicc")
report = gate.run_all()
print(f"SCORE: {report.overall_score:.3f}")
print(f"PASSED: {report.passed}")
print("FAILURES:")
for f in report.failures:
    print(" -", f)
