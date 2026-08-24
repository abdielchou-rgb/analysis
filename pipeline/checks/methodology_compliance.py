"""_check_methodology_compliance — 验证报告是否遵守注入的方法论规则"""

from __future__ import annotations

import re
from pathlib import Path


def check_methodology_compliance(report_text: str, report_type: str) -> dict:
    issues = []
    if not report_text or len(report_text) < 300:
        return {"passed": True, "issues": [], "score": 1.0}
    rules_path = Path(__file__).resolve().parent.parent.parent / "data" / "methodology_rules.json"
    if rules_path.exists():
        try:
            import json

            rules = json.loads(rules_path.read_text(encoding="utf-8"))
        except Exception:
            rules = {}
    else:
        rules = {}
    topic_signal = {
        "industry_lifecycle": ["生命周期", "成长", "成熟"],
        "profit_pool": ["利润池", "利润", "毛利率"],
        "competitive_forces": ["竞争", "格局", "壁垒"],
        "valuation": ["估值", "PE", "DCF"],
    }
    for topic, signals in topic_signal.items():
        if topic in rules:
            covered = any(signal in report_text for signal in signals)
            if not covered:
                issues.append(f"方法论覆盖缺失: {topic}")
    judgment_pat = r"我们判断[^。]*?(?:将|会|应)"
    for m in re.finditer(judgment_pat, report_text):
        ctx = report_text[max(0, m.start() - 50) : m.end() + 100]
        if not re.search(r"\d+\.?\d*\s*[%亿万千元]", ctx):
            issues.append(f"判断句缺数据支撑: {m.group(0)[:40]}")
            break
    passed = len(issues) == 0
    score = 1.0 if passed else max(0.3, 1.0 - 0.2 * len(issues))
    return {"passed": passed, "issues": issues[:5], "score": score}
