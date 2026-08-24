# -*- coding: utf-8 -*-
"""ma_synergy_engine.py — 并购协同三源量化（2026-08-08 框架 P2）

顶级打法：McKinsey 并购协同拆三源——revenue synergy / cost synergy / tax synergy，逐项量化。
  1. 收入协同：交叉销售/渠道共享/产品组合 → 增量收入 × 利润率
  2. 成本协同：产能共享/采购合并/管理精简 → 成本节省
  3. 税协同：亏损结转/税率差异/结构 → 税节省

用法：
  from core.compute.ma_synergy_engine import calculate_synergy, build_prompt
  result = calculate_synergy({...})
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.ma_synergy")


@dataclass
class SynergyResult:
    revenue_synergy: float = 0.0
    cost_synergy: float = 0.0
    tax_synergy: float = 0.0
    total_synergy: float = 0.0
    integration_risk: float = 0.0      # 0-1 整合风险
    npv_synergy: float = 0.0           # 协同 NPV（5年折现）
    details: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)


def calculate_synergy(params: dict) -> SynergyResult:
    """并购协同三源量化。

    params:
      target_revenue: 标的收入
      margin: 标的利润率
      cross_sell_pct: 交叉销售增量收入占比
      cost_save_pct: 成本节省占比
      tax_benefit_year: 年税节省
      integration_cost: 整合成本
      discount_rate: 折现率
      integration_years: 协同实现年数
    """
    r = SynergyResult()
    tr = float(params.get("target_revenue", 0))
    margin = float(params.get("margin", 0.1))
    cross_pct = float(params.get("cross_sell_pct", 0.03))
    cost_pct = float(params.get("cost_save_pct", 0.02))
    tax_year = float(params.get("tax_benefit_year", 0))
    icost = float(params.get("integration_cost", 0))
    disc = float(params.get("discount_rate", 0.1))
    years = int(params.get("integration_years", 5))

    # 1. 收入协同：交叉销售增量收入 × 利润率
    r.revenue_synergy = tr * cross_pct * margin
    # 2. 成本协同：成本节省 = 标的收入 × 节省占比（或按成本基数）
    r.cost_synergy = tr * cost_pct
    # 3. 税协同
    r.tax_synergy = tax_year
    # 合计年协同
    annual = r.revenue_synergy + r.cost_synergy + r.tax_synergy
    r.total_synergy = annual
    r.details = {
        "revenue_synergy": round(r.revenue_synergy, 2),
        "cost_synergy": round(r.cost_synergy, 2),
        "tax_synergy": round(r.tax_synergy, 2),
        "annual_total": round(annual, 2),
    }

    # 整合风险（简易：整合成本越大/协同实现越久 → 风险越高）
    if tr > 0:
        risk = min(0.9, icost / (tr * 3) + years * 0.05)
        r.integration_risk = round(risk, 2)
    else:
        r.integration_risk = 0.5

    # 协同 NPV（5年折现，扣除整合成本）
    cf = [annual] * years
    npv = sum(cf[t] / (1 + disc) ** (t + 1) for t in range(years)) - icost
    r.npv_synergy = round(npv, 2)

    r.reasons = [
        f"收入协同（交叉销售{params.get('cross_sell_pct',0.03):.0%}×利润率{margin:.0%}）: {r.revenue_synergy:,.0f}/年",
        f"成本协同（节省{cost_pct:.0%}）: {r.cost_synergy:,.0f}/年",
        f"税协同: {r.tax_synergy:,.0f}/年",
        f"整合风险: {r.integration_risk:.0%}",
        f"协同NPV（{years}年折现-整合成本）: {r.npv_synergy:,.0f}",
    ]
    return r


def build_prompt(r: SynergyResult) -> str:
    lines = ["=== 并购协同三源量化（McKinsey）===",
             f"收入协同: {r.revenue_synergy:,.0f}/年 | 成本协同: {r.cost_synergy:,.0f}/年 | "
             f"税协同: {r.tax_synergy:,.0f}/年 | 合计: {r.total_synergy:,.0f}/年",
             f"协同NPV: {r.npv_synergy:,.0f} | 整合风险: {r.integration_risk:.0%}"]
    for x in r.reasons:
        lines.append(f"- {x}")
    lines.append("=== 协同结束 ===")
    return "\n".join(lines)
