"""
1号分析师 V30 — SOTP分部加总估值模块

基于各业务分部的独立估值、加总得到公司整体价值。
支持 PE/PS/EV-EBITDA/DCF 等多种估值方法。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("v30.valuation.sotp")


@dataclass
class SOTPSegmentInput:
    name: str
    revenue_bn: float = 0.0
    profit_bn: float = 0.0
    valuation_method: str = "PE"
    peer_pe: Optional[float] = None
    peer_ps: Optional[float] = None
    peer_ev_ebitda: Optional[float] = None
    dcf_value: Optional[float] = None
    description: str = ""


@dataclass
class SOTPResult:
    company: str
    stock_code: str
    segments: list[dict] = field(default_factory=list)
    total_segments_value: float = 0.0
    cash_and_equivalents: float = 0.0
    net_debt: float = 0.0
    non_core_assets: float = 0.0
    equity_value: float = 0.0
    total_shares: int = 0
    target_price: float = 0.0
    warnings: list[str] = field(default_factory=list)


def compute_sotp(
    company: str,
    stock_code: str,
    segments: list[SOTPSegmentInput],
    cash_and_equivalents: float = 0.0,
    net_debt: float = 0.0,
    non_core_assets: float = 0.0,
    total_shares: Optional[int] = None,
) -> SOTPResult:
    if total_shares is None:
        total_shares = 0

    result = SOTPResult(
        company=company,
        stock_code=stock_code,
        cash_and_equivalents=cash_and_equivalents,
        net_debt=net_debt,
        non_core_assets=non_core_assets,
        total_shares=total_shares,
    )

    segment_results = []
    total_value = 0.0

    for seg in segments:
        seg_val = _calc_segment_value(seg)
        seg_dict = {
            "name": seg.name,
            "revenue_bn": seg.revenue_bn,
            "profit_bn": seg.profit_bn,
            "method": seg.valuation_method,
            "applied_multiple": seg_val["multiple"],
            "segment_value": seg_val["value"],
            "description": seg.description,
        }
        segment_results.append(seg_dict)
        total_value += seg_val["value"] if seg_val["value"] else 0.0

    result.segments = segment_results
    result.total_segments_value = round(total_value, 2)
    net_cash = cash_and_equivalents - net_debt
    result.equity_value = round(total_value + net_cash + non_core_assets, 2)

    if total_shares > 0:
        result.target_price = round(result.equity_value / (total_shares / 1e8), 2)
    else:
        result.warnings.append("总股本为0，无法计算每股目标价")

    return result


def _calc_segment_value(seg: SOTPSegmentInput) -> dict:
    method = seg.valuation_method
    value = None
    multiple = None

    if method == "PE" and seg.peer_pe and seg.profit_bn and seg.profit_bn > 0:
        multiple = seg.peer_pe
        value = seg.profit_bn * seg.peer_pe
    elif method == "PS" and seg.peer_ps and seg.revenue_bn and seg.revenue_bn > 0:
        multiple = seg.peer_ps
        value = seg.revenue_bn * seg.peer_ps
    elif method == "EV-EBITDA" and seg.peer_ev_ebitda:
        ebitda_est = seg.profit_bn * 1.2 if seg.profit_bn else seg.revenue_bn * 0.15
        if seg.peer_ev_ebitda and ebitda_est > 0:
            multiple = seg.peer_ev_ebitda
            value = ebitda_est * seg.peer_ev_ebitda
    elif method == "DCF" and seg.dcf_value:
        value = seg.dcf_value

    return {"value": round(value, 2) if value else 0.0, "multiple": multiple}


def format_sotp_for_report(result: SOTPResult) -> str:
    lines = []
    lines.append("### SOTP分部加总估值")
    lines.append("")
    lines.append("**标的**: %s (%s)" % (result.company, result.stock_code))
    lines.append("")

    headers = ["业务分部", "营收(亿元)", "净利(亿元)", "估值方法", "适用倍数", "分部估值(亿元)"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    for seg in result.segments:
        row = [
            seg["name"],
            "%.1f" % seg["revenue_bn"] if seg["revenue_bn"] else "N/A",
            "%.1f" % seg["profit_bn"] if seg["profit_bn"] else "N/A",
            seg["method"],
            str(seg["applied_multiple"]) if seg["applied_multiple"] else "N/A",
            "%.1f" % seg["segment_value"],
        ]
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("| **分部估值合计** | | | | | **%.2f** |" % result.total_segments_value)
    lines.append("| 加: 现金及等价物 | | | | | %.2f |" % result.cash_and_equivalents)
    lines.append("| 减: 净债务 | | | | | %.2f |" % result.net_debt)
    lines.append("| 加: 非核心资产 | | | | | %.2f |" % result.non_core_assets)
    lines.append("| **股权价值** | | | | | **%.2f** |" % result.equity_value)

    if result.target_price:
        lines.append("")
        lines.append(
            "**每股目标价: %.2f 元** (总股本 %.2f 亿股)"
            % (result.target_price, result.total_shares / 1e8 if result.total_shares else 0)
        )

    if result.warnings:
        lines.append("")
        lines.append("**警告**:")
        for w in result.warnings:
            lines.append("- " + w)

    return "\n".join(lines)
