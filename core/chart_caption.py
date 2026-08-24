"""
图注数据驱动渲染器（Chart Caption Data-Driven Renderer）— R49 二期

**问题**：图注由 patch 脚本硬编码字符串生成，绕过 data_dict → 净利 3.41 幻觉、
DCF 敏感性"最悲观仍高于当前价5%"等周期性复发。

**方案**（对标顶级打法"图注是数据的一部分，禁手写"）：
  从 enrich/data_dict 自动渲染图注，数值/占比/同比由模板拼装。
  禁止手写数字——所有数字必须从 data_dict 取。

**用法**：
  caption = render_chart_caption("financial_trends", data_dict, asset)
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("2hao.chart_caption")

_ROOT = Path(__file__).resolve().parent.parent


def _num(d: dict, *keys, default=None):
    """从 data_dict 提取数值（多键名兼容）。"""
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                pass
    return default


def render_chart_caption(chart_id: str, data_dict: dict, asset: str = "") -> str:
    """根据图表类型从 data_dict 渲染图注。

    Args:
        chart_id: 图表 id（fig_valuation / financial_trends / profit_margin 等）
        data_dict: 数据字典（含 revenue_trend_2025 / profitability_2025 等）
        asset: 标的名（用于图注称呼）

    Returns:
        图注文字（不含数字则返回空，调用方应写"数据缺口"）
    """
    if not data_dict:
        return ""
    d = data_dict
    name = asset or "公司"

    # financial_trends: 营收/净利趋势
    if chart_id in ("financial_trends", "fig_financial_trends"):
        rev_24 = _num(d, "revenue_trend_2024", "fig_revenue_trend_2024")
        rev_25 = _num(d, "revenue_trend_2025", "fig_revenue_trend_2025")
        prof_25 = _num(d, "profitability_2025", "fig_profitability_2025", "net_profit_2025", "归母净利_2025")
        prof_24 = _num(d, "profitability_2024", "fig_profitability_2024", "net_profit_2024", "归母净利_2024")
        parts = []
        if rev_25 and rev_24:
            growth = (rev_25 / rev_24 - 1) * 100
            parts.append(f"2025年营收{rev_25:.1f}亿元，同比+{growth:.1f}%")
        elif rev_25:
            parts.append(f"2025年营收{rev_25:.1f}亿元")
        if prof_25 and prof_24:
            pgrowth = (prof_25 / prof_24 - 1) * 100
            parts.append(f"归母净利{prof_25:.2f}亿元，同比{pgrowth:+.1f}%")
        elif prof_25:
            parts.append(f"归母净利{prof_25:.2f}亿元")
        if parts:
            return f"图中呈现了{name}近两年营收与净利趋势：" + "；".join(parts) + "。"
        return ""

    # profit_margin: 毛利率趋势
    if chart_id in ("profit_margin", "fig_profit_margin"):
        m25 = _num(d, "margin_2025", "fig_margin_2025", "毛利率_2025")
        m18 = _num(d, "margin_2018", "fig_margin_2018", "毛利率_2018")
        if m25:
            prefix = f"（2018年{m18:.1f}% → 2025年{m25:.1f}%）" if m18 else ""
            return f"图中展示毛利率趋势{prefix}，反映产品结构与成本控制变化。"
        return ""

    # fig_valuation: 估值/PE
    if chart_id in ("fig_valuation", "valuation_peers", "fig_valuation_peers"):
        pe = _num(d, "pe_ttm", "pe", "动态PE")
        ind_pe = _num(d, "industry_pe_ttm")
        if pe:
            extra = f"，行业中位{ind_pe:.1f}倍" if ind_pe else ""
            return f"图中对比{name}与可比公司估值：当前PE {pe:.1f}倍{extra}。"
        return ""

    # capital_flow: 资金面
    if chart_id in ("capital_flow", "fig_capital_flow"):
        north = _num(d, "capital_north_net_latest", "flow_north_net_latest")
        margin = _num(d, "capital_margin_balance_latest", "flow_margin_balance_latest")
        parts = []
        if margin:
            parts.append(f"融资余额{margin:.2f}亿元")
        if north is not None:
            parts.append(f"北向净流入{north:.2f}亿元")
        if parts:
            return "图中展示资金面：" + "，".join(parts) + "。"
        return ""

    # 默认：无模板
    return ""


def render_all_captions(data_dict: dict, asset: str = "") -> dict:
    """渲染所有已知图表的图注。返回 {chart_id: caption}。"""
    chart_ids = [
        "financial_trends",
        "profit_margin",
        "fig_valuation",
        "capital_flow",
    ]
    return {cid: render_chart_caption(cid, data_dict, asset) for cid in chart_ids}


if __name__ == "__main__":
    # 自测
    sample = {
        "revenue_trend_2024": 12.95,
        "revenue_trend_2025": 15.58,
        "profitability_2024": 2.61,
        "profitability_2025": 1.68,
        "margin_2018": 40.87,
        "margin_2025": 34.5,
        "pe_ttm": 78.1,
        "industry_pe_ttm": 46.56,
        "capital_margin_balance_latest": 5.7,
        "capital_north_net_latest": -67.75,
    }
    for cid, cap in render_all_captions(sample, "柯力传感").items():
        print(f"[{cid}] {cap}")
