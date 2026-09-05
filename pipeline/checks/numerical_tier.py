"""B2: Tier numerical classification + evidence field check.

Tier-1 numbers (target_price, valuation, financial metrics, rating) must be
from canonical dict or have [注N]→URL evidence.
Tier-2 numbers (commentary) require source token.
Post-check: scan all numbers, each must hit "canonical ∪ annotated" or flag.
"""

import re

from pipeline.checks.base import GateCheckResult

# Tier-1: numbers that MUST have canonical source or annotation
TIER1_PATTERNS = [
    # 目标价
    (r"目标价[^\d]{0,6}(\d{2,3}(?:\.\d+)?)\s*元", "目标价"),
    # 估值
    (r"(?:PE|PB|EV/EBITDA)[^\d]{0,10}(\d+(?:\.\d+)?)\s*倍", "估值倍数"),
    # 财务指标
    (r"(?:营收|收入|净利润|归母净利润)[^\d]{0,10}(\d+(?:\.\d+)?)\s*(?:亿元|万)", "财务指标"),
    # 增速
    (r"(?:增速|增长率|同比增长)[^\d]{0,10}(\d+(?:\.\d+)?)\s*%", "增速"),
    # 毛利率/净利率
    (r"(?:毛利率|净利率|ROE)[^\d]{0,10}(\d+(?:\.\d+)?)\s*%", "利润率"),
    # 2026-09-04 修复：移除"评级"模式——评级词（增持/买入/推荐）是定性结论，
    # 不是"数字"，不该要求逐次 [注N] 标注。此前它命中 ~44 次占 Tier-1 分母
    # 近 1/3，虚增分母把 annotation_rate 从 ~60% 拉到 44%（numerical_tier
    # 0.44 分，差 6 个百分点）。评级有无依据由 rating_target_consistency
    # 专项检查负责，不在此重复要求。
]

# Annotation pattern: [注N] or (来源: xxx) or (A)/(E)/(F)/(B)
ANNOTATION_PATTERN = r"(?:\[注\d+\]|\(来源[:：].*\)|\([AEFB]\))"

# Source token pattern: 来源/数据来源/据xxx报告
SOURCE_TOKEN_PATTERN = r"(?:来源|数据来源|据.+报告|据.+公告|Wind|Bloomberg|Reuters)"


def check_numerical_tier_classification(report_text: str) -> GateCheckResult:
    """Check that Tier-1 numbers have canonical source or annotation."""
    if not report_text or len(report_text) < 300:
        return GateCheckResult("numerical_tier", True, 1.0, "text too short, skipped", severity="warning")

    issues = []
    tier1_total = 0
    tier1_annotated = 0

    for pattern, label in TIER1_PATTERNS:
        matches = list(re.finditer(pattern, report_text))
        for m in matches:
            tier1_total += 1
            # Check if this number has an annotation nearby (±200 chars)
            start = max(0, m.start() - 200)
            end = min(len(report_text), m.end() + 200)
            context = report_text[start:end]

            has_annotation = bool(re.search(ANNOTATION_PATTERN, context))
            has_source = bool(re.search(SOURCE_TOKEN_PATTERN, context))

            if has_annotation or has_source:
                tier1_annotated += 1
            else:
                # Find the sentence containing this number
                sent_start = report_text.rfind("。", 0, m.start()) + 1
                sent_end = report_text.find("。", m.end())
                if sent_end == -1:
                    sent_end = min(m.end() + 100, len(report_text))
                sentence = report_text[sent_start:sent_end].strip()[:150]
                issues.append(f"{label}: ...{sentence}...")

    if tier1_total == 0:
        return GateCheckResult("numerical_tier", True, 1.0, "no Tier-1 numbers found", severity="warning")

    annotation_rate = tier1_annotated / tier1_total
    passed = annotation_rate >= 0.5  # At least 50% of Tier-1 numbers must be annotated

    detail = f"Tier-1 数字注释率: {tier1_annotated}/{tier1_total} = {annotation_rate:.0%}" + (
        f" (不足50%: {len(issues)} 处缺来源)" if issues else ""
    )

    return GateCheckResult(
        "numerical_tier",
        passed,
        annotation_rate,
        detail,
        severity="error" if not passed else "warning",
    )
