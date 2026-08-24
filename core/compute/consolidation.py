# -*- coding: utf-8 -*-
"""consolidation.py — 行业并购估值模块（R57 投行并购视角）

对标投行并购组：判断行业整合趋势、谁是整合者/被整合者、
并购估值倍数（EV/EBITDA）、资本配置效率（ROIC vs WACC）。

规则来源：methodology_consulting_deep.json（merger_integration）+ 投行并购方法论。
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("2hao.consolidation")

# EV/EBITDA 行业并购倍数基准（投行常用区间，需按行业校准）
# 数据来源：行业并购交易均值（2023-2026 样本）
_INDUSTRY_EV_EBITDA = {
    "半导体": 12.0, "光伏": 8.0, "锂电": 9.0, "医药": 14.0,
    "医疗器械": 15.0, "消费": 10.0, "化工": 7.0, "汽车": 6.0,
    "电力": 8.0, "房地产": 6.0, "银行": 9.0, "保险": 8.0,
    "科技": 13.0, "传感器": 10.0, "机器人": 12.0, "工控": 9.0,
}


def industry_ev_ebitda(industry: str, fallback: float = 10.0) -> float:
    """行业并购 EV/EBITDA 基准倍数。"""
    for k, v in _INDUSTRY_EV_EBITDA.items():
        if k in industry or industry in k:
            return v
    return fallback


def consolidation_assessment(
    industry: str = "",
    cr3: Optional[float] = None,
    cr5: Optional[float] = None,
    top_company_mcap_b: Optional[float] = None,
    top_company_revenue_b: Optional[float] = None,
    industry_total_mcap_b: Optional[float] = None,
) -> dict:
    """行业整合态势评估。

    Args:
        industry: 行业名（用于 EV/EBITDA 基准）
        cr3: 前3集中度（%）
        cr5: 前5集中度（%）
        top_company_mcap_b: 龙头市值（亿元）
        top_company_revenue_b: 龙头营收（亿元）
        industry_total_mcap_b: 行业总市值（亿元）

    Returns:
        {consolidation_stage, cr3, ev_ebitda_benchmark, top_share, top_is_consolidator, ...}
    """
    result = {
        "industry": industry,
        "cr3": cr3,
        "cr5": cr5,
        "ev_ebitda_benchmark": industry_ev_ebitda(industry),
    }

    # 整合阶段判断（按 CR3，对标投行行业整合 S 曲线）
    if cr3 is not None:
        if cr3 < 30:
            result["consolidation_stage"] = "分散期（整合早期）"
            result["stage_signal"] = "CR3<30%，行业分散，整合空间大（谁先整合谁受益）"
        elif cr3 < 50:
            result["consolidation_stage"] = "整合中（加速期）"
            result["stage_signal"] = "CR3 30-50%，整合加速，头部并购扩张窗口"
        elif cr3 < 70:
            result["consolidation_stage"] = "集中期（格局趋稳）"
            result["stage_signal"] = "CR3 50-70%，格局趋稳，龙头盈利质量提升"
        else:
            result["consolidation_stage"] = "寡头/稳态"
            result["stage_signal"] = "CR3>70%，寡头格局，龙头定价权强（三四规则：稳定3-4家）"

    # 龙头份额与整合者判断
    if top_company_mcap_b and industry_total_mcap_b and industry_total_mcap_b > 0:
        top_share = top_company_mcap_b / industry_total_mcap_b * 100
        result["top_share_pct"] = round(top_share, 1)
        result["top_is_consolidator"] = top_share > 25
        result["top_share_signal"] = (
            f"龙头占行业市值 {top_share:.0f}%，{'是' if top_share > 25 else '尚非'}整合者"
            f"（>25% 通常具备整合能力）")

    # 资本配置效率提示（ROIC vs WACC 由 compute 填入）
    result["capital_efficiency_note"] = (
        "资本配置效率：ROIC > WACC = 创造价值（整合者特征）；ROIC < WACC = 毁灭价值（被整合者候选）")

    return result


def consolidator_profile(
    roic: Optional[float] = None,
    wacc: Optional[float] = None,
    mcap_b: Optional[float] = None,
    net_cash_b: Optional[float] = None,
    revenue_growth: Optional[float] = None,
) -> dict:
    """整合者财务特征识别。

    整合者通常：ROIC > WACC（创造价值）、净现金（并购弹药）、收入增速 > 行业。
    被整合者通常：ROIC < WACC、现金流弱、市占下滑。
    """
    result = {}
    _scores = {"consolidator": 0, "target": 0}

    if roic is not None and wacc is not None:
        spread = roic - wacc
        result["roic_wacc_spread"] = round(spread, 2)
        if spread > 0.05:
            _scores["consolidator"] += 1
            result["value_creation"] = "创造价值（ROIC>WACC，整合者特征）"
        elif spread < -0.03:
            _scores["target"] += 1
            result["value_creation"] = "毁灭价值（ROIC<WACC，被整合者候选）"
        else:
            result["value_creation"] = "价值中性"

    if net_cash_b is not None and mcap_b:
        _cash_ratio = net_cash_b / mcap_b
        result["net_cash_ratio"] = round(_cash_ratio, 2)
        if _cash_ratio > 0.10:
            _scores["consolidator"] += 1
            result["m_and_a_ammo"] = f"净现金占市值 {_cash_ratio:.0%}，并购弹药充足"
        else:
            result["m_and_a_ammo"] = "净现金有限，并购需外部融资"

    _scores["role"] = "consolidator" if _scores["consolidator"] > _scores["target"] else (
        "target" if _scores["target"] > _scores["consolidator"] else "neutral")
    result["profile"] = _scores
    return result


if __name__ == "__main__":
    # 自测
    a = consolidation_assessment(industry="半导体", cr3=45, top_company_mcap_b=500,
                                 industry_total_mcap_b=1500)
    print("整合评估:", a["consolidation_stage"], "|", a["top_share_signal"])
    p = consolidator_profile(roic=0.12, wacc=0.08, mcap_b=500, net_cash_b=80)
    print("整合者画像:", p["value_creation"], "|", p["m_and_a_ammo"], "| role:", p["profile"]["role"])
