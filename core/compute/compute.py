"""Phase F: Numerical Compute Engine — DCF/可比/情景/收入桥。

从 V30 22K 行提取 4 个核心计算模型，纯 Python 重写。
输入: dict[年份, dict[指标, 值]] → 输出: dict

零外部依赖（不需要 pandas/numpy/akshare）。
所有财务假设硬编码合理默认值，不在 code 里留 TODO。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("v51.compute")


@dataclass
class DCFInput:
    """DCF valuation inputs with hardcoded sensible defaults."""
    free_cash_flow: float = 0.0          # 最近一年自由现金流（亿元）
    growth_years_1_5: float = 0.10       # 1-5年增长率
    growth_years_6_10: float = 0.05      # 6-10年增长率
    terminal_growth: float = 0.03        # 终值增长率
    wacc: float = 0.10                   # 加权平均资本成本
    net_debt: float = 0.0                # 净债务（有息负债-现金）
    shares_outstanding: float = 1.0      # 总股本（亿股）
    risk_free_rate: float = 0.025        # 无风险利率
    equity_risk_premium: float = 0.065   # 股权风险溢价
    beta: float = 1.0                    # Beta
    cost_of_debt: float = 0.04           # 债务成本


@dataclass
class DCFResult:
    fair_value_per_share: float = 0.0
    present_value_fcf: float = 0.0
    present_value_terminal: float = 0.0
    enterprise_value: float = 0.0
    equity_value: float = 0.0
    upside_pct: float = 0.0
    implied_pe: float = 0.0
    assumptions: dict = field(default_factory=dict)
    sensitivity_table: list = field(default_factory=list)


def run_dcf(inputs: DCFInput, current_price: float = 0.0,
            current_eps: float = 0.0) -> DCFResult:
    """Pure Python DCF valuation.

    Uses standard two-stage DCF + terminal value.
    No numpy/pandas — all manual loops.
    """
    result = DCFResult()
    wacc = inputs.wacc
    fcf = inputs.free_cash_flow

    # Stage 1: Years 1-5
    pv_fcf = 0.0
    fcf_year = fcf
    for year in range(1, 6):
        fcf_year *= (1 + inputs.growth_years_1_5)
        pv_fcf += fcf_year / ((1 + wacc) ** year)

    # Stage 2: Years 6-10
    for year in range(6, 11):
        fcf_year *= (1 + inputs.growth_years_6_10)
        pv_fcf += fcf_year / ((1 + wacc) ** year)

    result.present_value_fcf = round(pv_fcf, 2)

    # Terminal value (Gordon Growth)
    terminal_fcf = fcf_year * (1 + inputs.terminal_growth)
    terminal_value = terminal_fcf / (wacc - inputs.terminal_growth)
    result.present_value_terminal = round(terminal_value / ((1 + wacc) ** 10), 2)

    # Enterprise value
    result.enterprise_value = round(result.present_value_fcf + result.present_value_terminal, 2)

    # Equity value
    result.equity_value = round(result.enterprise_value - inputs.net_debt, 2)

    # Per share
    if inputs.shares_outstanding > 0:
        result.fair_value_per_share = round(result.equity_value / inputs.shares_outstanding, 2)

    # Upside
    if current_price > 0 and result.fair_value_per_share > 0:
        result.upside_pct = round(
            (result.fair_value_per_share - current_price) / current_price * 100, 1
        )

    # Implied PE
    if current_eps > 0 and result.fair_value_per_share > 0:
        result.implied_pe = round(result.fair_value_per_share / current_eps, 1)

    # Sensitivity table: WACC x terminal_growth
    for w in [wacc - 0.01, wacc, wacc + 0.01]:
        for tg in [inputs.terminal_growth - 0.005,
                    inputs.terminal_growth,
                    inputs.terminal_growth + 0.005]:
            if w <= tg:
                continue
            tv = terminal_fcf / (w - tg)
            pv_tv = tv / ((1 + w) ** 10)
            ev = pv_fcf + pv_tv
            eq = ev - inputs.net_debt
            per_share = round(eq / inputs.shares_outstanding, 2) if inputs.shares_outstanding > 0 else 0
            result.sensitivity_table.append({
                "wacc": round(w * 100, 1),
                "terminal_growth": round(tg * 100, 1),
                "fair_value": per_share,
            })

    result.assumptions = {
        "fcf_base": fcf,
        "growth_1_5": f"{inputs.growth_years_1_5*100:.0f}%",
        "growth_6_10": f"{inputs.growth_years_6_10*100:.0f}%",
        "terminal_growth": f"{inputs.terminal_growth*100:.0f}%",
        "wacc": f"{inputs.wacc*100:.0f}%",
        "net_debt": inputs.net_debt,
        "shares": inputs.shares_outstanding,
    }
    return result


# ── Comparable Valuation ──────────────────────────────────────

@dataclass
class ComparableResult:
    """可比估值结果。"""
    target_pe: float = 0.0
    target_pb: float = 0.0
    target_ev_ebitda: float = 0.0
    implied_pe_price: float = 0.0
    implied_pb_price: float = 0.0
    peers: list = field(default_factory=list)
    summary: str = ""


def run_comparable(company_eps: float, company_bvps: float,
                    company_ebitda: float = 0.0,
                    peer_pe_list: Optional[list[float]] = None,
                    peer_pb_list: Optional[list[float]] = None,
                    peer_ev_ebitda_list: Optional[list[float]] = None) -> ComparableResult:
    """可比公司估值。

    Args:
        company_eps: 公司每股收益
        company_bvps: 公司每股净资产
        company_ebitda: 公司 EBITDA/股
        peer_pe_list: 同业 PE 倍数列表
        peer_pb_list: 同业 PB 倍数列表
        peer_ev_ebitda_list: 同业 EV/EBITDA 列表

    Returns:
        ComparableResult with implied target prices.
    """
    result = ComparableResult()

    if peer_pe_list and len(peer_pe_list) >= 2 and company_eps > 0:
        median_pe = sorted(peer_pe_list)[len(peer_pe_list) // 2]
        mean_pe = sum(peer_pe_list) / len(peer_pe_list)
        result.target_pe = round(mean_pe, 1)
        result.implied_pe_price = round(company_eps * mean_pe, 2)
        result.peers.append({
            "metric": "PE", "median": median_pe, "mean": round(mean_pe, 1),
            "min": min(peer_pe_list), "max": max(peer_pe_list),
        })

    if peer_pb_list and len(peer_pb_list) >= 2 and company_bvps > 0:
        mean_pb = sum(peer_pb_list) / len(peer_pb_list)
        result.target_pb = round(mean_pb, 1)
        result.implied_pb_price = round(company_bvps * mean_pb, 2)
        result.peers.append({
            "metric": "PB", "mean": round(mean_pb, 1),
            "min": min(peer_pb_list), "max": max(peer_pb_list),
        })

    if peer_ev_ebitda_list and len(peer_ev_ebitda_list) >= 2 and company_ebitda > 0:
        mean_ev_ebitda = sum(peer_ev_ebitda_list) / len(peer_ev_ebitda_list)
        result.target_ev_ebitda = round(mean_ev_ebitda, 1)
        result.peers.append({
            "metric": "EV/EBITDA", "mean": round(mean_ev_ebitda, 1),
            "min": min(peer_ev_ebitda_list), "max": max(peer_ev_ebitda_list),
        })

    # Summary
    prices = []
    if result.implied_pe_price > 0:
        prices.append(("PE", result.implied_pe_price))
    if result.implied_pb_price > 0:
        prices.append(("PB", result.implied_pb_price))

    if prices:
        avg_price = sum(p for _, p in prices) / len(prices)
        result.summary = f"基于 {len(result.peers)} 种方法，隐含均价 {avg_price:.1f} 元"
    else:
        result.summary = "数据不足，无法进行可比估值"

    return result


# ── Scenario Analysis ──────────────────────────────────────────

@dataclass
class ScenarioResult:
    bull_price: float = 0.0
    base_price: float = 0.0
    bear_price: float = 0.0
    bull_prob: float = 0.25
    base_prob: float = 0.50
    bear_prob: float = 0.25
    weighted_target: float = 0.0
    upside: float = 0.0
    downside: float = 0.0
    risk_reward: float = 0.0


def run_scenario(current_price: float,
                  dcf_value: float,
                  comparable_value: float,
                  bull_premium: float = 0.20,
                  bear_discount: float = 0.20) -> ScenarioResult:
    """Three-scenario analysis with probability weighting.

    Args:
        current_price: 当前股价
        dcf_value: DCF 公允价值
        comparable_value: 可比法公允价值
        bull_premium: 乐观情景溢价比例
        bear_discount: 悲观情景折价比例

    Returns:
        ScenarioResult with weighted target and risk/reward.
    """
    result = ScenarioResult()
    base = (dcf_value + comparable_value) / 2 if dcf_value > 0 and comparable_value > 0 else max(dcf_value, comparable_value)

    result.base_price = round(base, 2)
    result.bull_price = round(base * (1 + bull_premium), 2)
    result.bear_price = round(base * (1 - bear_discount), 2)

    result.weighted_target = round(
        result.bull_price * result.bull_prob +
        result.base_price * result.base_prob +
        result.bear_price * result.bear_prob,
        2,
    )

    if current_price > 0:
        result.upside = round((result.weighted_target - current_price) / current_price * 100, 1)
        result.downside = round((result.bear_price - current_price) / current_price * 100, 1)
        result.risk_reward = round(result.upside / abs(result.downside), 2) if result.downside != 0 else 0

    return result


# ── Simple Revenue Bridge ──────────────────────────────────────

def run_revenue_bridge(segments: dict[str, float],
                        prior_revenue: float = 0.0) -> dict:
    """Simple revenue bridge decomposition.

    Args:
        segments: {"segment_name": revenue_value}
        prior_revenue: 上期总营收

    Returns:
        {"segments": {name: {"value": v, "pct_of_total": pct, "yoy_chg": ...}},
         "total": total,
         "bridge_waterfall": [{"label": ..., "value": ...}]}
    """
    if not segments:
        return {"error": "no segment data"}

    total = sum(segments.values())
    result = {
        "total": total,
        "segments": {},
        "bridge_waterfall": [
            {"label": "期初", "value": prior_revenue},
        ],
    }

    for name, value in sorted(segments.items(), key=lambda x: -x[1]):
        pct = round(value / total * 100, 1) if total > 0 else 0
        result["segments"][name] = {
            "value": value,
            "pct_of_total": pct,
        }
        result["bridge_waterfall"].append({
            "label": name,
            "value": round(value - prior_revenue / max(len(segments), 1), 1),
        })

    result["bridge_waterfall"].append({
        "label": "本期合计",
        "value": total,
    })

    return result


# ── Adapter for V51 KnowledgePackage ──────────────────────────

def compute_from_kp(price: float = 0.0, eps: float = 0.0,
                     bvps: float = 0.0, fcf: float = 0.0,
                     revenue: float = 0.0, net_profit: float = 0.0,
                     shares: float = 0.0, net_debt: float = 0.0,
                     peers_pe: Optional[list] = None,
                     segments: Optional[dict] = None,
                     current_price: float = 0.0) -> dict:
    """Run all compute models from KnowledgePackage data points.

    Returns dict with keys: dcf, comparable, scenario, revenue_bridge.
    """
    result = {}

    # DCF
    if fcf > 0 and shares > 0:
        dcf_input = DCFInput(
            free_cash_flow=fcf,
            shares_outstanding=shares,
            net_debt=net_debt,
        )
        dcf_result = run_dcf(dcf_input, current_price, eps)
        result["dcf"] = {
            "fair_value": dcf_result.fair_value_per_share,
            "upside_pct": dcf_result.upside_pct,
            "implied_pe": dcf_result.implied_pe,
            "assumptions": dcf_result.assumptions,
            "sensitivity": dcf_result.sensitivity_table,
        }

    # Comparable
    if eps > 0 and peers_pe and len(peers_pe) >= 2:
        comp = run_comparable(
            company_eps=eps, company_bvps=bvps,
            peer_pe_list=peers_pe,
        )
        result["comparable"] = {
            "implied_pe_price": comp.implied_pe_price,
            "target_pe": comp.target_pe,
            "summary": comp.summary,
            "peers": comp.peers,
        }

    # Scenario
    dcf_val = result.get("dcf", {}).get("fair_value", 0)
    comp_val = result.get("comparable", {}).get("implied_pe_price", 0)
    if (dcf_val > 0 or comp_val > 0) and current_price > 0:
        sc = run_scenario(current_price, dcf_val, max(comp_val, dcf_val * 0.8))
        result["scenario"] = {
            "bull": sc.bull_price,
            "base": sc.base_price,
            "bear": sc.bear_price,
            "weighted_target": sc.weighted_target,
            "upside_pct": sc.upside,
            "downside_pct": sc.downside,
            "risk_reward": sc.risk_reward,
        }

    # Revenue bridge
    if segments:
        result["revenue_bridge"] = run_revenue_bridge(segments, revenue)

    return result
