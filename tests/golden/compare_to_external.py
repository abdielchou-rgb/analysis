"""自产报告 vs 外部真实研报对比 — R80 Phase2 评估端独立。

把 2hao 产出与真实券商研报用同一组指标对比，量化差距。
指标：模板句/反方强度/洞察密度/数据溯源/篇幅。
用法：
    python tests/golden/compare_to_external.py "output/油位传感器_重做报告.md" "tests/golden_external/xx.pdf"
"""

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from core.template_blacklist import scan as template_scan


def extract_text(path: str) -> str:
    p = Path(path)
    if p.suffix == ".md":
        return p.read_text(encoding="utf-8", errors="ignore")
    if p.suffix in (".pdf", ".docx"):
        # 简版提取：pdf 用 pdfplumber 若可用
        try:
            import pdfplumber

            with pdfplumber.open(p) as pdf:
                return "".join(pg.extract_text() or "" for pg in pdf.pages)
        except Exception:
            return ""
    return ""


def metrics(text: str) -> dict:
    if not text:
        return {"error": "无法提取文本"}
    body = re.sub(r"```.*?```", "", text, flags=re.S)
    chars = len(re.sub(r"\s", "", body))
    tpl = template_scan(text)
    # 反方段落数
    counters = re.findall(r"(反方|证伪|Bear)", text)
    # 洞察：含数字+时间的判断句
    jd = re.findall(r"(?:我们判断|我们认为|预计|判断)[^。]{0,60}?\d[^。]{0,30}?", text)
    # 数据来源标注
    sources = re.findall(r"\((?:A|B|E|F)\)|来源[:：]|数据来源", text)
    return {
        "chars": chars,
        "template_hits": tpl["total_exact"],
        "counter_paras": len(set(counters)),
        "anchored_judgments": len(jd),
        "source_marks": len(sources),
    }


def compare(a_path: str, b_path: str):
    ta, tb = extract_text(a_path), extract_text(b_path)
    ma, mb = metrics(ta), metrics(tb)
    print(f"{'指标':<16} {'2hao产出':<12} {'外部研报':<12} 差距")
    print("-" * 52)
    for k in ("chars", "template_hits", "counter_paras", "anchored_judgments", "source_marks"):
        va, vb = ma.get(k, 0), mb.get(k, 0)
        diff = vb - va
        print(f"{k:<16} {va:<12} {vb:<12} {diff:+d}")
    return ma, mb


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        compare(sys.argv[1], sys.argv[2])
    else:
        print("用法: python tests/golden/compare_to_external.py <2hao报告> <外部研报>")
