"""expectation_gap_engine.py — 预期差量化（2026-08-08 框架 P2）

顶级打法：中金/高盛用"市场一致预期 vs 我们的测算"量化预期差。
  1. 一致预期 EPS/目标价/增速（consensus）
  2. 我们的测算（我们 EPS/目标价/增速）
  3. 预期差 = (我们的 - 一致) / 一致 → 判断"市场低估/高估"

用法：
  from core.compute.expectation_gap_engine import calculate_expectation_gap, build_prompt
  result = calculate_expectation_gap({...})
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.expectation_gap")


@dataclass
class ExpectationGapResult:
    gaps: list = field(default_factory=list)  # 各指标预期差
    overall_gap: float = 0.0  # 综合预期差（加权）
    direction: str = "中性"  # 市场低估/高估/中性
    reasons: list = field(default_factory=list)


def calculate_expectation_gap(metrics: list) -> ExpectationGapResult:
    """计算预期差。

    metrics: [{name, consensus, ours, weight}] 各指标一致预期 vs 我们的测算
    """
    r = ExpectationGapResult()
    if not metrics:
        return r

    total_w = 0.0
    weighted = 0.0
    for m in metrics:
        c = m.get("consensus", 0)
        o = m.get("ours", 0)
        w = m.get("weight", 1.0)
        if c == 0:
            gap = None
        else:
            gap = (o - c) / abs(c)
        r.gaps.append(
            {
                "name": m.get("name", "?"),
                "consensus": c,
                "ours": o,
                "gap": round(gap, 4) if gap is not None else None,
            }
        )
        if gap is not None:
            weighted += gap * w
            total_w += w
            if gap > 0.05:
                r.reasons.append(f"{m.get('name')} 我们的测算高于市场 {gap:.0%}（市场可能低估）")
            elif gap < -0.05:
                r.reasons.append(f"{m.get('name')} 我们的测算低于市场 {gap:.0%}（市场可能高估）")
            else:
                r.reasons.append(f"{m.get('name')} 与市场一致（{gap:+.1%}）")

    r.overall_gap = round(weighted / total_w, 4) if total_w else 0.0
    if r.overall_gap > 0.05:
        r.direction = "市场低估"
    elif r.overall_gap < -0.05:
        r.direction = "市场高估"
    else:
        r.direction = "中性"
    return r


def build_prompt(r: ExpectationGapResult) -> str:
    """生成注入个股研究的预期差说明。"""
    lines = ["=== 预期差量化（市场一致预期 vs 我们的测算）===", f"综合预期差: {r.overall_gap:+.1%}（{r.direction}）"]
    for g in r.gaps:
        if g["gap"] is not None:
            lines.append(f"- {g['name']}: 市场{g['consensus']:,.0f} vs 我们{g['ours']:,.0f}（{g['gap']:+.1%}）")
        else:
            lines.append(f"- {g['name']}: 无一致预期数据")
    for x in r.reasons:
        lines.append(f"- {x}")
    lines.append("=== 预期差结束 ===")
    return "\n".join(lines)
