"""
1号分析师 V30 — 三情景分析模型

基于摩根士丹利 Risk-Reward 框架，对 DCF 估值进行三情景分析：
  - 基准情景 (Base): 最可能的营收增长和利润率路径
  - 乐观情景 (Bull): 上行驱动全部实现
  - 悲观情景 (Bear): 下行风险全部兑现

输出概率加权目标价和风险收益比。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("v30.valuation.scenario")


@dataclass
class ScenarioDetail:
    """单情景的假设和结果。"""
    name: str
    probability: float                     # 概率 (0~1)
    revenue_growth_rates: list[float]      # 预测期逐年增速
    operating_margin: float                # 稳态营业利润率
    terminal_growth: float                 # 终值增长率
    pe_multiple: Optional[float] = None    # 可比 PE（可选，用于交叉验证）
    target_price: float = 0.0              # 该情景下的目标价
    description: str = ""                  # 情景描述


@dataclass
class ScenarioResult:
    """三情景分析结果。"""
    company: str
    stock_code: str
    scenarios: dict[str, dict] = field(default_factory=dict)
    weighted_target_price: float = 0.0         # 概率加权目标价
    risk_reward_ratio: Optional[float] = None   # (上行空间*概率) / (下行空间*概率)
    upside: Optional[float] = None              # 上行空间 %
    downside: Optional[float] = None            # 下行空间 %
    warnings: list[str] = field(default_factory=list)


def compute_scenario(
    company: str,
    stock_code: str,
    base_price: float,           # 当前股价（用于计算风险收益比）
    base_scenario: ScenarioDetail,
    bull_scenario: ScenarioDetail,
    bear_scenario: ScenarioDetail,
    # DCF 计算共享参数
    wacc: float = 0.09,
    projection_years: int = 5,
    tax_rate: float = 0.25,
    target_da_pct_revenue: float = 0.03,
    target_capex_pct_revenue: float = 0.04,
    target_wc_pct_revenue: float = 0.02,
    # 基准营收
    base_revenue: Optional[float] = None,
    total_shares: Optional[int] = None,
    net_debt: float = 0.0,
) -> ScenarioResult:
    """
    执行三情景分析。

    每个情景独立运行简化 DCF，计算目标价后按概率加权。

    Args:
        company: 公司名称
        stock_code: 股票代码
        base_price: 当前股价（元）
        base_scenario: 基准情景
        bull_scenario: 乐观情景
        bear_scenario: 悲观情景
        wacc: 加权平均资本成本（三情景共用）
        projection_years: 预测期年数
        tax_rate: 税率
        target_da_pct_revenue: D&A 占营收比
        target_capex_pct_revenue: CapEx 占营收比
        target_wc_pct_revenue: 营运资本变动占营收比
        base_revenue: 基准年营收（亿元）
        total_shares: 总股本
        net_debt: 净债务（亿元）

    Returns:
        ScenarioResult: 三情景分析结果
    """
    scenarios = {}
    warnings = []
    probability_sum = sum([
        base_scenario.probability,
        bull_scenario.probability,
        bear_scenario.probability,
    ])

    if abs(probability_sum - 1.0) > 0.01:
        warnings.append(f"概率和={probability_sum:.2f}，不等于1，将归一化")
        # 归一化
        total = probability_sum
        base_scenario.probability /= total
        bull_scenario.probability /= total
        bear_scenario.probability /= total

    if base_revenue is None:
        base_revenue = 100.0  # 默认100亿
        warnings.append("基准营收未指定，使用默认值100亿元")

    if total_shares is None:
        total_shares = 1_000_000_000
        warnings.append("总股本未指定，使用默认值10亿股")

    scenario_inputs = {
        "base": base_scenario,
        "bull": bull_scenario,
        "bear": bear_scenario,
    }

    shares_yi = total_shares / 1e8 if total_shares else 1.0

    for key, scenario in scenario_inputs.items():
        target_price = _run_scenario_dcf(
            base_revenue=base_revenue,
            growth_rates=scenario.revenue_growth_rates,
            operating_margin=scenario.operating_margin,
            terminal_growth=scenario.terminal_growth,
            projection_years=projection_years,
            wacc=wacc,
            tax_rate=tax_rate,
            da_pct=target_da_pct_revenue,
            capex_pct=target_capex_pct_revenue,
            wc_pct=target_wc_pct_revenue,
            net_debt=net_debt,
            shares_yi=shares_yi,
        )

        scenarios[key] = {
            "name": scenario.name,
            "probability": scenario.probability,
            "target_price": target_price,
            "revenue_growth_rates": scenario.revenue_growth_rates,
            "operating_margin": scenario.operating_margin,
            "terminal_growth": scenario.terminal_growth,
            "description": scenario.description,
        }

    # ── 概率加权目标价 ──
    weighted_price = sum(
        s["target_price"] * s["probability"] for s in scenarios.values()
    )

    # ── 风险收益比 ──
    base_tp = scenarios["base"]["target_price"]
    bull_tp = scenarios["bull"]["target_price"]
    bear_tp = scenarios["bear"]["target_price"]
    bull_prob = bull_scenario.probability
    bear_prob = bear_scenario.probability

    upside = round((bull_tp / base_price - 1) * 100, 2) if base_price > 0 else 0
    downside = round((bear_tp / base_price - 1) * 100, 2) if base_price > 0 else 0

    # 上行空间 × 上行概率 vs 下行空间 × 下行概率
    upside_weighted = max(0, bull_tp - base_price) * bull_prob
    downside_weighted = max(0, base_price - bear_tp) * bear_prob

    risk_reward = round(upside_weighted / downside_weighted, 2) if downside_weighted > 0 else None

    return ScenarioResult(
        company=company,
        stock_code=stock_code,
        scenarios=scenarios,
        weighted_target_price=round(weighted_price, 2),
        risk_reward_ratio=risk_reward,
        upside=upside,
        downside=downside,
        warnings=warnings,
    )


# ═══════════════════════════════════════════════════════════
# 默认情景工厂
# ═══════════════════════════════════════════════════════════


def make_base_scenario(
    revenue_growth_rates: Optional[list[float]] = None,
    operating_margin: float = 0.20,
    terminal_growth: float = 0.03,
    probability: float = 0.55,
    description: str = "",
) -> ScenarioDetail:
    """创建基准情景（默认概率55%）。"""
    if revenue_growth_rates is None:
        revenue_growth_rates = [0.10, 0.09, 0.08, 0.07, 0.06]
    return ScenarioDetail(
        name="基准情景 (Base)",
        probability=probability,
        revenue_growth_rates=revenue_growth_rates,
        operating_margin=operating_margin,
        terminal_growth=terminal_growth,
        description=description or "基于当前趋势的合理预期",
    )


def make_bull_scenario(
    revenue_growth_rates: Optional[list[float]] = None,
    operating_margin: float = 0.25,
    terminal_growth: float = 0.04,
    probability: float = 0.20,
    description: str = "",
) -> ScenarioDetail:
    """创建乐观情景（默认概率20%）。"""
    if revenue_growth_rates is None:
        revenue_growth_rates = [0.18, 0.16, 0.14, 0.12, 0.10]
    return ScenarioDetail(
        name="乐观情景 (Bull)",
        probability=probability,
        revenue_growth_rates=revenue_growth_rates,
        operating_margin=operating_margin,
        terminal_growth=terminal_growth,
        description=description or "上行驱动全部实现——市场份额提升、利润率改善",
    )


def make_bear_scenario(
    revenue_growth_rates: Optional[list[float]] = None,
    operating_margin: float = 0.12,
    terminal_growth: float = 0.02,
    probability: float = 0.25,
    description: str = "",
) -> ScenarioDetail:
    """创建悲观情景（默认概率25%）。"""
    if revenue_growth_rates is None:
        revenue_growth_rates = [0.03, 0.03, 0.02, 0.02, 0.02]
    return ScenarioDetail(
        name="悲观情景 (Bear)",
        probability=probability,
        revenue_growth_rates=revenue_growth_rates,
        operating_margin=operating_margin,
        terminal_growth=terminal_growth,
        description=description or "下行风险兑现——竞争加剧、宏观经济放缓",
    )


# ═══════════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════════


def _run_scenario_dcf(
    base_revenue: float,
    growth_rates: list[float],
    operating_margin: float,
    terminal_growth: float,
    projection_years: int,
    wacc: float,
    tax_rate: float,
    da_pct: float,
    capex_pct: float,
    wc_pct: float,
    net_debt: float,
    shares_yi: float,
) -> float:
    """
    对单个情景运行简化 DCF。

    Returns:
        target_price: 目标价（元/股）
    """
    current_rev = base_revenue

    for i in range(min(len(growth_rates), projection_years)):
        current_rev *= (1 + growth_rates[i])

    # 用最后一年的营收做终值计算
    terminal_revenue = current_rev
    ebit = terminal_revenue * operating_margin
    nopat = ebit * (1 - tax_rate)
    da = terminal_revenue * da_pct
    capex = terminal_revenue * capex_pct
    wc_change = terminal_revenue * wc_pct
    terminal_fcf = nopat + da - capex - wc_change

    # 逐期 FCF 折现
    pv_fcf_sum = 0.0
    current_rev = base_revenue
    for i in range(projection_years):
        rev = current_rev * (1 + growth_rates[i])
        ebit_i = rev * operating_margin
        nopat_i = ebit_i * (1 - tax_rate)
        da_i = rev * da_pct
        capex_i = rev * capex_pct
        wc_i = rev * wc_pct
        fcf_i = nopat_i + da_i - capex_i - wc_i
        pv_fcf_sum += fcf_i / ((1 + wacc) ** (i + 1))
        current_rev = rev

    # 终值
    if wacc > terminal_growth:
        terminal_value = terminal_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    else:
        terminal_value = terminal_fcf * 15  # 保守15倍

    pv_terminal = terminal_value / ((1 + wacc) ** projection_years)
    enterprise_value = pv_fcf_sum + pv_terminal
    equity_value = enterprise_value - net_debt
    target_price = equity_value / shares_yi if shares_yi > 0 else 0

    return round(target_price, 2)


def format_scenario_for_report(sr: ScenarioResult) -> str:
    """将三情景分析格式化为报告文本块。"""
    lines = []
    lines.append(f"## 三情景分析: {sr.company}")
    lines.append("")

    # 汇总
    lines.append(f"**概率加权目标价: {sr.weighted_target_price:.2f} 元**")
    if sr.risk_reward_ratio is not None:
        lines.append(f"**风险收益比: {sr.risk_reward_ratio:.2f}x** (上行概率加权/下行概率加权)")
    if sr.upside is not None:
        lines.append(f"**上行空间: +{sr.upside:.1f}% | 下行空间: {sr.downside:.1f}%**")
    lines.append("")

    # 三情景详情
    lines.append("| 情景 | 概率 | 营收增速 | 利润率 | 终值增长率 | 目标价(元) | 描述 |")
    lines.append("|------|------|---------|--------|-----------|-----------|------|")

    scenario_order = ["base", "bull", "bear"]
    for key in scenario_order:
        s = sr.scenarios.get(key, {})
        growth_str = f"{s.get('revenue_growth_rates', [0])[0]*100:.0f}%→{s.get('revenue_growth_rates', [0])[-1]*100:.0f}%"
        lines.append(
            f"| {s.get('name', key)} | {s.get('probability', 0)*100:.0f}% | "
            f"{growth_str} | {s.get('operating_margin', 0)*100:.0f}% | "
            f"{s.get('terminal_growth', 0)*100:.0f}% | "
            f"{s.get('target_price', 0):.2f} | {s.get('description', '')} |"
        )
    lines.append("")

    # 警告
    if sr.warnings:
        lines.append("**警告**:")
        for w in sr.warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)
