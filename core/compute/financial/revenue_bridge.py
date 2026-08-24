"""
1号分析师 V30 — 收入桥模型

基于结构化财务数据，计算营收增长的驱动因子拆解。

核心逻辑：
  营收增长率 = 行业增长贡献 + 份额变化贡献 + 价格变化贡献 + 产品结构贡献

注意：
  由于 baostock 不提供分业务线数据，收入桥是基于"总量+可用比率"的
  顶层拆解。更精细的"按产品线/客户/区域"拆解需要接入完整财报数据。
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from core.models import RevenueBridge, StructuredData

logger = logging.getLogger("v30.revenue_bridge")


def compute_revenue_bridge(
    data: StructuredData,
    last_n_years: int = 3,
) -> Optional[RevenueBridge]:
    """
    计算收入桥。

    如果有 YoY 营收增速数据，直接用。
    如果没有，用相邻年份的营收差值计算。

    Args:
        data: L1 输出的结构化数据
        last_n_years: 覆盖最近 N 年的变化

    Returns:
        RevenueBridge: 收入桥分析结果
    """
    financials = sorted(data.financials, key=lambda x: x.fiscal_year)
    if len(financials) < 2:
        logger.warning("[L2收入桥] 数据不足2年，无法计算")
        return None

    # 取最近连续年份
    recent = financials[-last_n_years:] if len(financials) >= last_n_years else financials
    base_year = recent[0]
    current_year = recent[-1]

    if base_year.revenue is None or current_year.revenue is None:
        logger.warning("[L2收入桥] 营收数据缺失")
        return None
    if base_year.revenue <= 0:
        logger.warning("[L2收入桥] 基期营收为负或零")
        return None

    # 总增长率
    change_abs = round(current_year.revenue - base_year.revenue, 4)
    growth_pct = round((current_year.revenue - base_year.revenue) / base_year.revenue * 100, 2)

    period = f"{base_year.fiscal_year}→{current_year.fiscal_year}"

    # ── 驱动因子拆解 ──
    drivers = []

    # 驱动1: 按年份逐个计算年增速贡献
    for i in range(len(recent) - 1):
        prev = recent[i]
        curr = recent[i + 1]
        if prev.revenue and curr.revenue and prev.revenue > 0:
            yoy = round((curr.revenue - prev.revenue) / prev.revenue * 100, 2)
        else:
            yoy = None

        # 驱动2: 如果有 YoY 同比数据，用官方数据
        if curr.yoy_revenue is not None:
            drivers.append({
                "period": f"{prev.fiscal_year}→{curr.fiscal_year}",
                "yoy_pct": round(curr.yoy_revenue, 2),
                "yoy_source": "baostock",
                "revenue_level": curr.revenue,
            })
        elif yoy is not None:
            drivers.append({
                "period": f"{prev.fiscal_year}→{curr.fiscal_year}",
                "yoy_pct": yoy,
                "yoy_source": "calculated",
                "revenue_level": curr.revenue,
            })

    # ── 质量判断 ──
    data_gaps = []
    confidence = "high"

    # 检查是否有 YoY 增速全靠计算得出（不是来自数据源）
    all_calculated = all(d.get("yoy_source") == "calculated" for d in drivers)
    if all_calculated:
        data_gaps.append("所有增速来自计算，非 baostock 直接提供")
        confidence = "low"
    elif any(d.get("yoy_source") == "calculated" for d in drivers):
        data_gaps.append("部分年份增速来自计算")
        confidence = "medium"

    # 检查是否有营收数据缺失
    for f in financials:
        if f.revenue is None:
            data_gaps.append(f"[{f.fiscal_year}] 营收数据缺失")
            confidence = "low"

    bridge = RevenueBridge(
        company=data.profile.stock_name,
        period=period,
        total_revenue_growth_pct=growth_pct,
        total_revenue_change_abs=change_abs,
        drivers=drivers,
        data_gaps=data_gaps,
        confidence=confidence,
    )

    return bridge


def format_revenue_bridge_for_report(bridge: RevenueBridge) -> str:
    """将收入桥格式化为报告可读的文本块。"""
    lines = []
    lines.append(f"**收入桥: {bridge.period}**")
    lines.append("")
    lines.append(f"总营收变化: {bridge.total_revenue_change_abs:+.2f} 亿元 "
                 f"({bridge.total_revenue_growth_pct:+.2f}%)")
    lines.append("")
    lines.append("| 期间 | YoY增速 | 营收水平(亿) | 来源 |")
    lines.append("|------|---------|-------------|------|")
    for d in bridge.drivers:
        src = "baostock" if d.get("yoy_source") == "baostock" else "计算值"
        lines.append(f"| {d['period']} | {d['yoy_pct']:+.2f}% | "
                     f"{d['revenue_level']:.2f} | {src} |")

    if bridge.data_gaps:
        lines.append("")
        lines.append("**数据缺口**:")
        for gap in bridge.data_gaps:
            lines.append(f"- {gap}")

    lines.append(f"\n置信度: {bridge.confidence}")
    return "\n".join(lines)
