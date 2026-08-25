"""
1号分析师 V30 — 费用桥模型

基于结构化财务数据，分析费用结构变化。

核心逻辑：
  总费用率 ≈ 1 - 净利率 - 营业利润率差距
  分项费用采用"总量+比率推断"方法

数据限制：
  baostock 不提供逐项费用数据（销售费用/管理费用/研发费用/财务费用）。
  因此费用桥采用"总量+比率推断"方法：
  - 用已知的营收和净利，推断费用总额
  - 用已知的毛利率和净利率差距，推断三项费用占比
  - 明确标记为"推断"而非"精确计算"

注意：
  真正的逐项费用拆解需要接入完整利润表数据（如来自 cninfo 或 akshare 的完整财报）。
"""

from __future__ import annotations

import logging
from typing import Optional

from core.models import ExpenseBridge, StructuredData

logger = logging.getLogger("v30.expense_bridge")

# 费用结构标签阈值配置
# 研发费用率高于此值视为"研发驱动型"
RD_INTENSIVE_THRESHOLD = 0.05  # 5%
# 推算的三项费用率中，销售+管理占比高于此值视为"销售驱动型"
SGA_INTENSIVE_THRESHOLD = 0.25  # 25%


def _estimate_sganda_rate(
    implied_opex_rate: float,
    industry: Optional[str] = None,
) -> float:
    """
    估算销售+管理费用率。

    研发费用率通常较稳定，可以基于行业经验值估算。
    对于大多数行业，研发费用占总费用的比例在 10-30% 之间。

    Args:
        implied_opex_rate: 推算的期间费用率（占总营收比例）
        industry: 行业名称，用于调整估算基准

    Returns:
        float: 估算的销售+管理费用率
    """
    # 假设研发费用约占期间费用的 15%（保守估计）
    # 财务费用约占期间费用的 5%
    # 其余为销售+管理费用
    estimated_rd_ratio_of_opex = 0.15
    estimated_finance_ratio_of_opex = 0.05

    if industry:
        # 基于行业调整估算比例
        industry_lower = industry.lower()
        # 科技/医药行业研发费用占比更高
        rd_intensive_keywords = [
            "科技",
            "信息",
            "软件",
            "医药",
            "生物",
            "半导体",
            "电子",
            "通信",
            "计算机",
            "医疗",
            "创新",
        ]
        if any(kw in industry_lower for kw in rd_intensive_keywords):
            estimated_rd_ratio_of_opex = 0.30
            estimated_finance_ratio_of_opex = 0.03
        # 金融/地产行业财务费用占比更高
        finance_intensive_keywords = [
            "银行",
            "证券",
            "保险",
            "房地产",
            "金融",
        ]
        if any(kw in industry_lower for kw in finance_intensive_keywords):
            estimated_finance_ratio_of_opex = 0.20
            estimated_rd_ratio_of_opex = 0.05
        # 消费/制造行业销售费用占比更高
        sales_intensive_keywords = [
            "消费",
            "食品",
            "饮料",
            "白酒",
            "零售",
            "家电",
            "汽车",
        ]
        if any(kw in industry_lower for kw in sales_intensive_keywords):
            estimated_rd_ratio_of_opex = 0.08
            estimated_finance_ratio_of_opex = 0.03

    remaining = 1.0 - estimated_rd_ratio_of_opex - estimated_finance_ratio_of_opex
    return implied_opex_rate * remaining


def _estimate_rd_rate(
    implied_opex_rate: float,
    industry: Optional[str] = None,
) -> float:
    """
    估算研发费用率。

    Args:
        implied_opex_rate: 推算的期间费用率（占总营收比例）
        industry: 行业名称

    Returns:
        float: 估算的研发费用率
    """
    estimated_rd_ratio_of_opex = 0.15
    estimated_finance_ratio_of_opex = 0.05

    if industry:
        industry_lower = industry.lower()
        rd_intensive_keywords = [
            "科技",
            "信息",
            "软件",
            "医药",
            "生物",
            "半导体",
            "电子",
            "通信",
            "计算机",
            "医疗",
            "创新",
        ]
        if any(kw in industry_lower for kw in rd_intensive_keywords):
            estimated_rd_ratio_of_opex = 0.30
        sales_intensive_keywords = [
            "消费",
            "食品",
            "饮料",
            "白酒",
            "零售",
            "家电",
            "汽车",
        ]
        if any(kw in industry_lower for kw in sales_intensive_keywords):
            estimated_rd_ratio_of_opex = 0.08
        finance_intensive_keywords = [
            "银行",
            "证券",
            "保险",
            "房地产",
            "金融",
        ]
        if any(kw in industry_lower for kw in finance_intensive_keywords):
            estimated_rd_ratio_of_opex = 0.05

    return implied_opex_rate * estimated_rd_ratio_of_opex


def _estimate_finance_rate(
    implied_opex_rate: float,
    industry: Optional[str] = None,
) -> float:
    """
    估算财务费用率。

    Args:
        implied_opex_rate: 推算的期间费用率（占总营收比例）
        industry: 行业名称

    Returns:
        float: 估算的财务费用率
    """
    estimated_finance_ratio_of_opex = 0.05

    if industry:
        industry_lower = industry.lower()
        finance_intensive_keywords = [
            "银行",
            "证券",
            "保险",
            "房地产",
            "金融",
        ]
        if any(kw in industry_lower for kw in finance_intensive_keywords):
            estimated_finance_ratio_of_opex = 0.20
        rd_intensive_keywords = [
            "科技",
            "信息",
            "软件",
            "医药",
            "生物",
            "半导体",
            "电子",
            "通信",
            "计算机",
            "医疗",
            "创新",
        ]
        if any(kw in industry_lower for kw in rd_intensive_keywords):
            estimated_finance_ratio_of_opex = 0.03
        sales_intensive_keywords = [
            "消费",
            "食品",
            "饮料",
            "白酒",
            "零售",
            "家电",
            "汽车",
        ]
        if any(kw in industry_lower for kw in sales_intensive_keywords):
            estimated_finance_ratio_of_opex = 0.03

    return implied_opex_rate * estimated_finance_ratio_of_opex


def compute_expense_bridge(
    data: StructuredData,
    last_n_years: int = 3,
) -> Optional[ExpenseBridge]:
    """
    计算费用桥。

    由于 baostock 不提供逐项费用数据，采用"总量+比率推断"方法：
    1. 计算期间费用总额 ≈ 营收 × (1 - 营业利润率 - 粗略税率)
    2. 基于行业特征推断分项费用比例
    3. 明确标注所有推断数据

    Args:
        data: L1 输出的结构化数据
        last_n_years: 覆盖最近 N 年

    Returns:
        ExpenseBridge: 费用桥分析结果，或 None（数据不足时）
    """
    financials = sorted(data.financials, key=lambda x: x.fiscal_year)
    if len(financials) < 2:
        logger.warning("[L2费用桥] 数据不足2年，无法计算")
        return None

    recent = financials[-last_n_years:] if len(financials) >= last_n_years else financials
    base_year = recent[0]
    current_year = recent[-1]
    industry = data.profile.industry

    period = f"{base_year.fiscal_year}→{current_year.fiscal_year}"

    expense_rates = []
    data_gaps = []

    # 固定标记：所有分项数据均为推断
    data_gaps.append("baostock 不提供逐项费用数据，分项费用率为基于总量的推断值")

    # 逐年份计算费用推估
    for f in recent:
        year = f.fiscal_year
        revenue = f.revenue
        gross_margin = f.gross_margin
        net_margin = f.net_margin

        if revenue is None or revenue <= 0:
            logger.warning(f"[L2费用桥] {year} 营收数据不可用")
            continue
        if gross_margin is None:
            logger.warning(f"[L2费用桥] {year} 毛利率缺失，跳过")
            continue

        # ── 方法一：从毛利率和净利率差距推算费用率 ──
        # 毛利率 → 营业利润率之间的差距主要是期间费用
        # 净利率 vs 营业利润率的差距主要是税率和非经常性损益
        # 期间费用率 ≈ 毛利率 - 净利率 - 税率影响(约 15% × 净利率)
        # 对于大部分公司，粗略近似：
        #   营业利润率 ≈ 毛利率 - 期间费用率
        #   净利率 ≈ 营业利润率 × (1 - 税率)
        # 因此：期间费用率 ≈ 毛利率 - 净利率 / (1 - 所得税率)

        # 估算所得税率（基于经验值，约 15%-25%）
        estimated_tax_rate = 0.20  # 默认 20%
        if industry:
            industry_lower = industry.lower()
            # 高新技术企业 15%
            high_tech_keywords = [
                "科技",
                "信息",
                "软件",
                "半导体",
                "电子",
                "医药",
                "生物",
                "计算机",
            ]
            if any(kw in industry_lower for kw in high_tech_keywords):
                estimated_tax_rate = 0.15
            # 一般企业 25%
            normal_tax_keywords = [
                "消费",
                "食品",
                "饮料",
                "零售",
                "房地产",
                "建筑",
                "制造",
            ]
            if any(kw in industry_lower for kw in normal_tax_keywords):
                estimated_tax_rate = 0.25

        # 推算营业利润率（除税前）
        if net_margin is not None and net_margin != 0:
            # 净利率 = 营业利润率 × (1 - 税率)
            # 所以 营业利润率 ≈ 净利率 / (1 - 税率)
            implied_operating_margin = round(net_margin / (1 - estimated_tax_rate), 4)
        else:
            # 如果没有净利率，直接用毛利率做粗略估算
            implied_operating_margin = round(gross_margin * 0.6, 4)

        # 推算期间费用率 = 毛利率 - 营业利润率
        # 注意：这包含了所有期间费用（销售+管理+研发+财务）
        implied_opex_rate = round(gross_margin - implied_operating_margin, 4)

        # 确保费用率合理（不能为负，不能超过毛利率）
        if implied_opex_rate < 0:
            implied_opex_rate = 0.0
            data_gaps.append(f"[{year}] 推算费用率为负，设为 0%（毛利率={gross_margin}%, 净利率={net_margin}%）")
        if implied_opex_rate > gross_margin:
            implied_opex_rate = gross_margin
            data_gaps.append(f"[{year}] 推算费用率超过毛利率，约束为 {gross_margin}%")

        # 推算营业利润率
        operating_margin = round(gross_margin - implied_opex_rate, 4)

        # ── 方法二：精度验证 ──
        # 检查推算的一致性：毛利率 - 费用率 ≈ 净利率 / (1-税率)
        expected_operating_margin = None
        if net_margin is not None:
            expected_operating_margin = round(net_margin / (1 - estimated_tax_rate), 4)

        gap_bp = None
        if expected_operating_margin is not None and operating_margin != 0:
            gap_bp = round(abs(operating_margin - expected_operating_margin) * 100, 2)

        # ── 分项费用推算（基于行业经验值） ──
        estimated_sganda = round(_estimate_sganda_rate(implied_opex_rate, industry), 4)
        estimated_rd = round(_estimate_rd_rate(implied_opex_rate, industry), 4)
        estimated_finance = round(_estimate_finance_rate(implied_opex_rate, industry), 4)

        # ── 数据质量标记 ──
        if net_margin is None:
            data_quality = "low"
            data_gaps.append(f"[{year}] 净利率缺失，费用推算精度受限")
        elif gap_bp and gap_bp > 5.0:
            data_quality = "low"
            data_gaps.append(f"[{year}] 推算一致性偏差较大（{gap_bp}bp），可能受非经常性损益影响")
        elif implied_opex_rate == 0:
            data_quality = "low"
        else:
            data_quality = "medium"

        expense_rates.append(
            {
                "year": year,
                "imputed": True,  # 标记所有分项为推算值
                "implied_operating_expense_rate": implied_opex_rate,
                "estimated_sganda_rate": estimated_sganda,
                "estimated_rd_rate": estimated_rd,
                "estimated_finance_rate": estimated_finance,
                "operating_margin": operating_margin,
                "net_margin": net_margin,
                "gross_margin": gross_margin,
                "implied_tax_rate": estimated_tax_rate,
                "gap_bp": gap_bp,
                "data_quality": data_quality,
            }
        )

    if len(expense_rates) < 2:
        logger.warning("[L2费用桥] 推算后有效年份不足2年")
        return None

    # ── 费用结构趋势分析 ──
    expense_structure_trend = _analyze_expense_trend(expense_rates, industry)
    margin_gap_trend = _analyze_margin_gap(expense_rates)

    # ── 置信度判断 ──
    confidence = "medium"
    low_quality_years = [e for e in expense_rates if e.get("data_quality") == "low"]
    if len(low_quality_years) > len(expense_rates) / 2:
        confidence = "low"
        data_gaps.append("超过半数年份数据质量偏低")

    bridge = ExpenseBridge(
        company=data.profile.stock_name,
        period=period,
        expense_rates=expense_rates,
        expense_structure_trend=expense_structure_trend,
        margin_gap_trend=margin_gap_trend,
        data_gaps=data_gaps,
        confidence=confidence,
    )

    return bridge


def _analyze_expense_trend(
    expense_rates: list[dict],
    industry: Optional[str] = None,
) -> str:
    """
    分析费用结构变化趋势。

    关注点：
    - 研发费用率是否在提升（研发投入增加是好信号）
    - 销售费用率是否稳定或下降（销售效率是否提升）
    - 总费用率趋势

    Returns:
        str: 费用结构趋势描述
    """
    if len(expense_rates) < 2:
        return "数据不足以分析趋势"

    first = expense_rates[0]
    last = expense_rates[-1]

    trends = []

    # 总费用率趋势
    first_opex = first.get("implied_operating_expense_rate", 0)
    last_opex = last.get("implied_operating_expense_rate", 0)
    opex_change = last_opex - first_opex

    if abs(opex_change) < 0.5:
        trends.append(f"总费用率基本稳定（{first_opex:.1f}%→{last_opex:.1f}%）")
    elif opex_change > 0:
        trends.append(f"总费用率上升 {opex_change:+.1f} 百分点（{first_opex:.1f}%→{last_opex:.1f}%）")
    else:
        trends.append(f"总费用率下降 {opex_change:+.1f} 百分点（{first_opex:.1f}%→{last_opex:.1f}%）")

    # 研发费用率趋势
    first_rd = first.get("estimated_rd_rate", 0)
    last_rd = last.get("estimated_rd_rate", 0)
    rd_change = last_rd - first_rd

    if rd_change > 0.5:
        trends.append(f"研发费用率提升 {rd_change:+.1f} 百分点，研发投入增加")
    elif rd_change < -0.5:
        trends.append(f"研发费用率下降 {rd_change:+.1f} 百分点，需关注研发投入是否充足")

    # 研发强度判断
    if last_rd >= RD_INTENSIVE_THRESHOLD * 100:
        trends.append(f"研发费用率达 {last_rd:.1f}%，属于研发驱动型公司")
    elif last_rd > 0:
        trends.append(f"研发费用率 {last_rd:.1f}%，研发投入水平一般")

    return "；".join(trends)


def _analyze_margin_gap(expense_rates: list[dict]) -> str:
    """
    分析营业利润率 vs 净利率的差距变化。

    差距主要由税率和非经常性损益造成。
    差距扩大可能是税率上升或非经常性损失增加。

    Returns:
        str: 利润率差距趋势描述
    """
    if len(expense_rates) < 2:
        return "数据不足以分析利润率差距"

    observations = []

    for e in expense_rates:
        year = e.get("year")
        op_margin = e.get("operating_margin")
        net_margin = e.get("net_margin")

        if op_margin is None or net_margin is None:
            continue

        gap = round(op_margin - net_margin, 2)

        # 税率影响
        tax_rate = e.get("implied_tax_rate", 0.20)
        expected_gap = round(op_margin * tax_rate, 2)

        non_recurring = round(gap - expected_gap, 2)

        observations.append(
            {
                "year": year,
                "gap": gap,
                "expected_tax_gap": expected_gap,
                "non_recurring_impact": non_recurring,
            }
        )

    if not observations:
        return "无可用利润率数据"

    # 差距变化趋势
    first_gap = observations[0]["gap"]
    last_gap = observations[-1]["gap"]
    gap_change = last_gap - first_gap

    trend_parts = []
    if abs(gap_change) < 1.0:
        trend_parts.append(f"利润率差距基本稳定（约 {last_gap:.1f} 百分点）")
    elif gap_change > 0:
        trend_parts.append(f"利润率差距扩大 {gap_change:+.1f} 百分点，税负或非经常性损失影响增加")
    else:
        trend_parts.append(f"利润率差距缩小 {gap_change:+.1f} 百分点，税负或非经常性影响改善")

    # 非经常性损益影响
    avg_non_recurring = round(sum(o["non_recurring_impact"] for o in observations) / len(observations), 2)
    if abs(avg_non_recurring) > 2.0:
        if avg_non_recurring > 0:
            trend_parts.append(f"非经常性损益平均拉低利润率 {avg_non_recurring:.1f} 百分点")
        else:
            trend_parts.append(f"非经常性损益平均提升利润率 {abs(avg_non_recurring):.1f} 百分点")

    return "；".join(trend_parts)


def format_expense_bridge_for_report(bridge: ExpenseBridge) -> str:
    """将费用桥格式化为报告可读的文本块。

    格式参考券商研报的费用分析表：
    | 指标 | 年份1 | 年份2 | 年份3 | 趋势 |
    """
    lines = []
    lines.append(f"**费用桥: {bridge.period}**")
    lines.append("")

    if not bridge.expense_rates:
        lines.append("(无有效数据)")
        return "\n".join(lines)

    # 表头
    years = [str(e["year"]) for e in bridge.expense_rates]
    lines.append("| 指标 | " + " | ".join(years) + " | 数据来源 |")
    lines.append("|" + "|".join(["---"] * (len(years) + 2)) + "|")

    # 总费用率
    opex_vals = [f"{e['implied_operating_expense_rate']:.1f}%" for e in bridge.expense_rates]
    lines.append("| 期间费用率(推算) | " + " | ".join(opex_vals) + " | 推算 |")

    # 销售+管理费用率（推算）
    sganda_vals = [f"{e['estimated_sganda_rate']:.1f}%" for e in bridge.expense_rates]
    lines.append("| 销售+管理费用率(估) | " + " | ".join(sganda_vals) + " | 行业估算 |")

    # 研发费用率（推算）
    rd_vals = [f"{e['estimated_rd_rate']:.1f}%" for e in bridge.expense_rates]
    lines.append("| 研发费用率(估) | " + " | ".join(rd_vals) + " | 行业估算 |")

    # 财务费用率（推算）
    fin_vals = [f"{e['estimated_finance_rate']:.1f}%" for e in bridge.expense_rates]
    lines.append("| 财务费用率(估) | " + " | ".join(fin_vals) + " | 行业估算 |")

    # 毛利率
    gm_vals = [f"{e.get('gross_margin', 0):.1f}%" for e in bridge.expense_rates]
    lines.append("| 毛利率 | " + " | ".join(gm_vals) + " | baostock |")

    # 营业利润率
    op_vals = [f"{e['operating_margin']:.1f}%" for e in bridge.expense_rates]
    lines.append("| 营业利润率(推算) | " + " | ".join(op_vals) + " | 推算 |")

    # 净利率
    nm_vals = []
    for e in bridge.expense_rates:
        nm = e.get("net_margin")
        nm_vals.append(f"{nm:.1f}%" if nm is not None else "N/A")
    lines.append("| 净利率 | " + " | ".join(nm_vals) + " | baostock |")

    # 利润率差距
    gap_vals = []
    for e in bridge.expense_rates:
        op = e.get("operating_margin", 0)
        nm = e.get("net_margin")
        if nm is not None:
            gap_vals.append(f"{op - nm:.1f}%")
        else:
            gap_vals.append("N/A")
    lines.append("| 营业利润率-净利率 | " + " | ".join(gap_vals) + " | 推算 |")

    lines.append("")

    # 趋势分析
    if bridge.expense_structure_trend:
        lines.append("**费用结构趋势**:")
        lines.append(f"  {bridge.expense_structure_trend}")
        lines.append("")

    if bridge.margin_gap_trend:
        lines.append("**利润率差距分析**:")
        lines.append(f"  {bridge.margin_gap_trend}")
        lines.append("")

    # 数据缺口
    if bridge.data_gaps:
        lines.append("**数据缺口**:")
        for gap in bridge.data_gaps:
            lines.append(f"- {gap}")

    lines.append(f"\n置信度: {bridge.confidence}")
    return "\n".join(lines)
