# -*- coding: utf-8 -*-
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"D:\2hao-analyst\output\柯力传感深度分析报告_v5_20260804.md"
text = open(p, encoding="utf-8").read()

# 剥离 YAML front matter
if text.startswith("---"):
    parts = text.split("---", 2)
    if len(parts) == 3:
        text = parts[2]

sections = re.split(
    r"(?:^## |^[一二三四五六七八九十百]+[、.．]|^第[一二三四五六七八九十百]+部分)", text, flags=re.MULTILINE
)
_appendix_marks = ("附录", "数据图表", "数据补充来源", "AGENT_ENRICH", "免责声明", "来源")
sections = [s for s in sections if not any(m in s[:30] for m in _appendix_marks)]

chain_patterns = [
    r"\u56e0\u6b64",
    r"\u8fd9\u610f\u5473\u7740",
    r"\u6211\u4eec\u5224\u65ad",
    r"\u6211\u4eec\u5efa\u8bae",
    r"\u7efc\u4e0a\u6240\u8ff0",
    r"\u56e0\u6b64\u6211\u4eec\u8ba4\u4e3a",
    r"\u5bfc\u81f4",
    r"\u4ece\u800c",
    r"\u5f71\u54cd",
    r"\u610f\u5473\u7740",
    r"So\s*What",
    r"\u6570\u636e\u8868\u660e",
    r"\u5bf9\u6295\u8d44\u8005\u610f\u5473\u7740",
    r"\u7efc\u5408\u5224\u65ad",
    r"\u6982\u7387\u8bc4\u4f30",
    r"\u8bc1\u4f2a\u6761\u4ef6",
    r"\u53cd\u65b9\u8bba\u8bc1",
    r"\u5224\u65ad[：:]",
]


def _is_table_section(sec):
    lines = [l.strip() for l in sec.split("\n") if l.strip()]
    if not lines:
        return False
    table_lines = sum(1 for l in lines if l.startswith("|") and l.endswith("|"))
    ratio = table_lines / len(lines)
    return ratio >= 0.6 or (table_lines >= 3 and len(sec) < 400)


for i, sec in enumerate(sections):
    if len(sec) < 50:
        continue
    if _is_table_section(sec):
        continue
    hits = sum(1 for p in chain_patterns if re.search(p, sec))
    expected = max(2, len(sec) // 300)
    score = min(hits / expected, 1.0)
    head = sec.strip().split("\n")[0][:50]
    print(f"[{i:2d}] len={len(sec):5d} hits={hits:2d} exp={expected:2d} score={score:.2f} | {head}")
