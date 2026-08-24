"""
1号分析师 V30 — 毛利桥模型

基于结构化财务数据，计算毛利率变化的驱动因子拆解。

核心逻辑：
  毛利率变化 = 价格效应 + 成本效应 + 产品结构效应 + 汇率/良率效应

注意：
  baostock 提供的是整体毛利率，不按产品线拆分。
  因此毛利桥是基于"整体毛利率变化 + 已知环境因素推断"的拆解。
  真正精细的按产品线毛利拆解需要完整分业务线数据。
"""

from __future__ import annotations

import logging
from typing import Optional

from core.models import MarginBridge, StructuredData

logger = logging.getLogger("v30.margin_bridge")


def compute_margin_bridge(
    data: StructuredData,
) -> Optional[MarginBridge]:
    """
    计算毛利桥。

    Args:
        data: L1 输出的结构化数据

    Returns:
        MarginBridge: 毛利桥分析结果
    """
    financials = sorted(data.financials, key=lambda x: x.fiscal_year)
    if len(financials) < 2:
        logger.warning("[L2毛利桥] 数据不足2年")
        return None

    # 用最近两个完整年份
    prev = financials[-2]
    curr = financials[-1]

    if prev.gross_margin is None or curr.gross_margin is None:
        logger.warning("[L2毛利桥] 毛利率数据缺失")
        return None

    prev_margin = prev.gross_margin
    current_margin = curr.gross_margin
    change = round(current_margin - prev_margin, 4)

    period = f"{prev.fiscal_year}→{curr.fiscal_year}"

    # ── 驱动因子推断 ──
    # 注意：这里是基于总量数据的推断，不是精确计算
    # 精确拆解需要分业务线的收入和成本数据
    drivers = []
    data_gaps = []

    # 固定标记：baostock 不分业务线，所以所有拆解都是推断
    data_gaps.append(
        "baostock 不分业务线数据，毛利桥驱动因子为结构推断"
    )

    # 如果毛利率基本不变，只有一个总量因子
    if abs(change) < 0.5:
        drivers.append({
            "driver": "总体稳定",
            "contribution_bp": round(change * 100, 2),
            "description": f"毛利率基本稳定，从 {prev_margin}% 到 {current_margin}%",
        })
    else:
        # 有变化时，记录变化幅度
        drivers.append({
            "driver": "毛利率变化",
            "contribution_bp": round(change * 100, 2),
            "description": f"整体毛利率 {prev_margin}% → {current_margin}%"
                          f"（{change:+.2f} 百分点）",
        })
        # 注明变化来源需要更细粒度数据才能拆解
        data_gaps.append(
            "毛利率变化的精细拆解（价格/成本/结构）需要分业务线数据"
        )

    # ── 置信度判断 ──
    confidence = "low"  # 因为没有分业务线数据

    bridge = MarginBridge(
        company=data.profile.stock_name,
        period=period,
        gross_margin_prev=prev_margin,
        gross_margin_current=current_margin,
        gross_margin_change=change,
        drivers=drivers,
        data_gaps=data_gaps,
        confidence=confidence,
    )

    return bridge


def format_margin_bridge_for_report(bridge: MarginBridge) -> str:
    """将毛利桥格式化为报告可读的文本块。"""
    lines = []
    lines.append(f"**毛利桥: {bridge.period}**")
    lines.append("")
    lines.append(f"毛利率: {bridge.gross_margin_prev}% → {bridge.gross_margin_current}% "
                 f"({bridge.gross_margin_change:+.2f} 百分点)")
    lines.append("")
    lines.append("| 驱动因子 | 贡献(bp) | 说明 |")
    lines.append("|---------|---------|------|")
    for d in bridge.drivers:
        lines.append(f"| {d['driver']} | {d['contribution_bp']:+.2f} | {d['description']} |")

    if bridge.data_gaps:
        lines.append("")
        lines.append("**数据缺口**:")
        for gap in bridge.data_gaps:
            lines.append(f"- {gap}")

    lines.append(f"\n置信度: {bridge.confidence}")
    return "\n".join(lines)
