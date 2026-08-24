"""unlisted_deep.py — 非上市深化估值（P2-2，2026-08-07）

补非上市标的（如久通物联）的深度：现有 unlisted_reverse 只做营收×PS 反向定价，
缺可比融资/股权结构/退出路径/里程碑估值。本模块补四块：

  1. 可比融资（VC/PE 轮次倍数）：用可比公司融资估值/营收倍数
  2. 股权结构风险：创始人持股/质押/代持 → 治理风险分
  3. 退出路径概率：IPO/并购/下一轮 三路径概率 + 时间窗口
  4. 里程碑估值：按业务里程碑（订单/产能/收入）分段估值

用法：
  from core.compute.unlisted_deep import calculate_unlisted_deep, format_summary
  r = calculate_unlisted_deep({
      "revenue": 50000000,          # 营收（元）
      "gross_margin": 0.35,         # 毛利率
      "comparable_ps": [3, 5, 8],   # 可比公司 PS 倍数
      "founder_holding": 0.60,      # 创始人持股
      "pledged": 0.20,              # 质押比例
      "milestones": [               # 里程碑（营收目标/估值）
          {"name": "当前", "revenue": 50000000, "months": 0},
          {"name": "12个月", "revenue": 80000000, "months": 12},
          {"name": "24个月", "revenue": 120000000, "months": 24},
      ],
  })
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.unlisted_deep")


@dataclass
class UnlistedDeepResult:
    # 可比融资
    ps_range: tuple = (0.0, 0.0)  # 可比 PS 区间
    implied_value_range: tuple = (0.0, 0.0)  # 隐含估值区间（营收×PS）
    median_value: float = 0.0  # 中值估值
    # 股权治理
    governance_risk: float = 0.0  # 0-1 治理风险
    governance_note: str = ""
    # 退出路径
    exit_paths: list = field(default_factory=list)  # [{path, prob, horizon}]
    # 里程碑估值
    milestones: list = field(default_factory=list)
    final_value_24m: float = 0.0  # 24个月里程碑估值
    verdict: str = ""
    reasons: list = field(default_factory=list)
    assumptions: dict = field(default_factory=dict)


def calculate_unlisted_deep(params: dict) -> UnlistedDeepResult:
    r = UnlistedDeepResult()
    r.assumptions = dict(params)
    revenue = float(params.get("revenue", 0) or 0)
    gm = float(params.get("gross_margin", 0.3) or 0)
    ps_list = [float(x) for x in params.get("comparable_ps", [3, 5, 8]) if x]
    founder = float(params.get("founder_holding", 0.6) or 0)
    pledged = float(params.get("pledged", 0.2) or 0)
    milestones = params.get("milestones", [])

    # 1. 可比融资估值
    if revenue > 0 and ps_list:
        lo, hi = min(ps_list), max(ps_list)
        r.ps_range = (lo, hi)
        r.implied_value_range = (revenue * lo, revenue * hi)
        r.median_value = revenue * sorted(ps_list)[len(ps_list) // 2]

    # 2. 股权治理风险（持股集中 + 质押）
    risk = 0.0
    note = []
    if founder < 0.3:
        risk += 0.3
        note.append("创始人持股<30%，控制力弱")
    elif founder < 0.5:
        risk += 0.15
        note.append("创始人持股<50%，需一致行动人")
    if pledged > 0.3:
        risk += 0.3
        note.append(f"质押比例{pledged:.0%}>30%，爆仓风险")
    elif pledged > 0.1:
        risk += 0.15
        note.append(f"质押比例{pledged:.0%}，需关注")
    if not note:
        note.append("股权结构健康")
    r.governance_risk = min(risk, 1.0)
    r.governance_note = "; ".join(note)

    # 3. 退出路径概率（并购/IPO/下一轮）
    # 简单启发式：并购为主（非上市常态），IPO 视规模
    r.exit_paths = [
        {"path": "并购", "prob": 0.5, "horizon": "12-24个月"},
        {"path": "IPO", "prob": 0.25 if revenue > 80000000 else 0.10, "horizon": "24-36个月"},
        {"path": "下一轮融资", "prob": 0.30, "horizon": "6-12个月"},
    ]

    # 4. 里程碑估值（按营收目标 × 可比 PS 中值）
    if revenue > 0 and ps_list:
        med_ps = sorted(ps_list)[len(ps_list) // 2]
        for m in milestones:
            rev_m = float(m.get("revenue", 0))
            val = rev_m * med_ps
            r.milestones.append({"name": m.get("name"), "revenue": rev_m, "value": val, "months": m.get("months")})
        if r.milestones:
            r.final_value_24m = r.milestones[-1]["value"]

    # 结论
    reasons = []
    if r.median_value > 0:
        reasons.append(f"可比融资中值估值 {r.median_value / 1e4:.0f}万（PS {sorted(ps_list)[len(ps_list) // 2]:.0f}x）")
    reasons.append(f"治理风险 {r.governance_risk:.0%}: {r.governance_note}")
    reasons.append(f"退出以并购为主(50%)，IPO概率 {r.exit_paths[1]['prob']:.0%}")
    if r.final_value_24m > 0:
        reasons.append(
            f"24个月里程碑估值 {r.final_value_24m / 1e4:.0f}万（隐含增速 {((r.milestones[-1]['revenue'] / revenue) - 1) if revenue else 0:.0%}）"
        )
    r.reasons = reasons

    if r.governance_risk > 0.5:
        r.verdict = "估值可行但治理风险高，需先解决股权/质押问题"
    elif r.exit_paths[1]["prob"] > 0.15:
        r.verdict = "估值合理，有 IPO 期权，建议推进"
    else:
        r.verdict = "估值以并购退出为主，需明确并购方匹配度"
    return r


def format_summary(r: UnlistedDeepResult) -> str:
    lines = [
        "=== 非上市深化估值 ===",
        f"可比融资估值区间: {r.implied_value_range[0] / 1e4:.0f}~{r.implied_value_range[1] / 1e4:.0f}万（中值 {r.median_value / 1e4:.0f}万）",
        f"治理风险: {r.governance_risk:.0%}（{r.governance_note}）",
        "退出路径: " + ", ".join(f"{p['path']}({p['prob']:.0%},{p['horizon']})" for p in r.exit_paths),
    ]
    if r.milestones:
        lines.append("里程碑估值: " + ", ".join(f"{m['name']}={m['value'] / 1e4:.0f}万" for m in r.milestones))
    lines.append(f"结论: {r.verdict}")
    for x in r.reasons:
        lines.append(f"  - {x}")
    lines.append("=== 结束 ===")
    return "\n".join(lines)
