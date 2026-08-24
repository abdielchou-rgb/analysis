# -*- coding: utf-8 -*-
"""golden dataset 校验 — R78 Phase1.5。

对 tests/golden/*.md 样本做确定性断言（无需 LLM）：
  1. 篇幅：>5000 字
  2. 结构：含标题/章节
  3. 判断密度：含观点词
  4. 数据密度：含数字
  5. 反方论证：含风险/证伪
  6. 无 AI 免责声明

用法：
    python tests/golden/golden_check.py            # 校验全部样本
    python tests/golden/golden_check.py --one x.md # 校验单份
"""
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
GOLDEN_DIR = _ROOT

# 判断词（JP）——专业报告观点表述
JP_WORDS = ["我们判断", "我们看好", "我们认为", "预计", "判断", "核心观点",
            "评级", "目标价", "风险提示", "我们认为"]
# 反方词——反方论证/风险
CP_WORDS = ["风险", "证伪", "反方", "担忧", "不确定性", "制约", "挑战",
            "如果", "假设", "不成立", "下行"]


def _extract_body(text: str) -> str:
    """去 frontmatter/AIGC 头。"""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i, l in enumerate(lines[1:], 1):
            if l.strip() == "---":
                return "\n".join(lines[i+1:])
    return text


def check_one(path: Path) -> dict:
    text = _extract_body(path.read_text(encoding="utf-8"))
    body = re.sub(r"```.*?```", "", text, flags=re.S)  # 去代码块
    chars = len(re.sub(r"\s", "", body))
    has_heading = bool(re.search(r"^#{1,3}\s", body, re.M))
    jp_hits = sum(1 for w in JP_WORDS if w in body)
    num_count = len(re.findall(r"\d+\.?\d*\s*(?:亿|万|%|倍|元)", body))
    cp_hits = sum(1 for w in CP_WORDS if w in body)
    ai_disclaimer = "内容由AI生成" in body or "AI辅助" in body or "仅供参考" in body[:2000]

    checks = {
        "chars": chars,
        "has_heading": has_heading,
        "jp_count": jp_hits,
        "data_points": num_count,
        "cp_count": cp_hits,
        "no_ai_disclaimer": not ai_disclaimer,
    }
    # 阈值
    results = {
        "chars_ok": chars >= 5000,
        "heading_ok": has_heading,
        "judgment_ok": jp_hits >= 5,
        "data_ok": num_count >= 20,
        "counter_ok": cp_hits >= 3,
        "no_ai_ok": not ai_disclaimer,
    }
    return {"file": path.name, "metrics": checks, "results": results}


def main():
    files = [Path(a) for a in sys.argv[1:] if a.endswith(".md")]
    if not files:
        files = sorted(GOLDEN_DIR.glob("*.md"))
    all_ok = True
    for f in files:
        r = check_one(f)
        ok = all(r["results"].values())
        all_ok = all_ok and ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {r['file']}: chars={r['metrics']['chars']} "
              f"jp={r['metrics']['jp_count']} data={r['metrics']['data_points']} "
              f"cp={r['metrics']['cp_count']} heading={r['metrics']['has_heading']} "
              f"no_ai={r['metrics']['no_ai_disclaimer']}")
        if not ok:
            for k, v in r["results"].items():
                if not v:
                    print(f"    ✗ {k}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
