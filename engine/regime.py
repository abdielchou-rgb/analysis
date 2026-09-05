"""
Regime-Conditional DCF + Synthetic Peers — 参考 Finverse 架构。
按经济体制加权 DCF，无清洁对标时合成虚拟 peer。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from engine.precision import D, ddiv


class EconomicRegime(str, Enum):
    EXPANSION = "expansion"  # 扩张期
    SLOWDOWN = "slowdown"  # 放缓期
    CONTRACTION = "contraction"  # 收缩期
    CRISIS = "crisis"  # 危机期


@dataclass
class RegimeProfile:
    """单个经济体制的参数"""

    regime: EconomicRegime
    probability: float = 0.25
    revenue_growth_adj: float = 0.0  # 相对基准的增速调整
    margin_adj: float = 0.0  # 相对基准的利润率调整
    wacc_adj: float = 0.0  # 相对基准的 WACC 调整
    terminal_growth_adj: float = 0.0  # 相对基准的终值增长率调整


@dataclass
class RegimeAssumptions:
    """Regime-Conditional DCF 假设"""

    ticker: str
    company_name: str
    base_revenue: float
    base_ebit_margin: float
    forecast_years: int = 5
    revenue_growth_rates: List[float] = field(default_factory=list)
    ebit_margins: List[float] = field(default_factory=list)
    da_pct_revenue: float = 0.03
    capex_pct_revenue: float = 0.04
    wc_pct_revenue: float = 0.02
    tax_rate: float = 0.25
    wacc: float = 0.09
    terminal_growth_rate: float = 0.03
    net_debt: float = 0.0
    shares_outstanding: float = 1.0
    current_price: Optional[float] = None
    regimes: Dict[EconomicRegime, RegimeProfile] = field(default_factory=dict)

    def __post_init__(self):
        if not self.regimes:
            self.regimes = {
                EconomicRegime.EXPANSION: RegimeProfile(EconomicRegime.EXPANSION, 0.30, 0.03, 0.02, -0.01, 0.005),
                EconomicRegime.SLOWDOWN: RegimeProfile(EconomicRegime.SLOWDOWN, 0.40, 0.0, 0.0, 0.0, 0.0),
                EconomicRegime.CONTRACTION: RegimeProfile(EconomicRegime.CONTRACTION, 0.20, -0.03, -0.02, 0.01, -0.005),
                EconomicRegime.CRISIS: RegimeProfile(EconomicRegime.CRISIS, 0.10, -0.08, -0.05, 0.03, -0.01),
            }


@dataclass
class RegimeDCFResult:
    """Regime-Conditional DCF 结果"""

    regime_values: Dict[str, float] = field(default_factory=dict)
    weighted_value: float = 0.0
    regime_contributions: Dict[str, float] = field(default_factory=dict)
    regime_probabilities: Dict[str, float] = field(default_factory=dict)
    upside_pct: Optional[float] = None


class RegimeDCFEngine:
    """Regime-Conditional DCF 引擎"""

    def __init__(self, assumptions: RegimeAssumptions):
        self.a = assumptions

    def run(self) -> RegimeDCFResult:
        result = RegimeDCFResult()
        a = self.a
        total_weighted = D(0)

        for regime, profile in a.regimes.items():
            # 调整参数
            adj_growth = [g + profile.revenue_growth_adj for g in a.revenue_growth_rates]
            adj_margin = [m + profile.margin_adj for m in a.ebit_margins]
            adj_wacc = a.wacc + profile.wacc_adj
            adj_terminal_g = a.terminal_growth_rate + profile.terminal_growth_adj

            # 确保 WACC > terminal growth
            if adj_wacc <= adj_terminal_g:
                adj_wacc = adj_terminal_g + 0.02

            # 计算该体制下的 DCF
            dcf_value = self._compute_dcf(adj_growth, adj_margin, adj_wacc, adj_terminal_g)

            result.regime_values[regime.value] = dcf_value
            result.regime_probabilities[regime.value] = profile.probability

            weighted = dcf_value * profile.probability
            result.regime_contributions[regime.value] = weighted
            total_weighted += D(weighted)

        result.weighted_value = float(total_weighted)

        if a.current_price and a.current_price > 0:
            result.upside_pct = (result.weighted_value / a.current_price - 1) * 100

        return result

    def _compute_dcf(
        self,
        growth_rates: List[float],
        margins: List[float],
        wacc: float,
        terminal_g: float,
    ) -> float:
        """单体制 DCF 计算"""
        a = self.a
        curr_rev = D(a.base_revenue)
        pv_fcf = D(0)

        for i in range(a.forecast_years):
            curr_rev = curr_rev * D(1 + growth_rates[i])
            ebit = curr_rev * D(margins[i])
            da = curr_rev * D(a.da_pct_revenue)
            capex = curr_rev * D(a.capex_pct_revenue)
            wc = curr_rev * D(a.wc_pct_revenue)
            nopat = ebit * D(1 - a.tax_rate)
            fcf = nopat + da - capex - wc
            df = D(1) / (D(1 + wacc) ** (i + 1))
            pv_fcf += fcf * df

        # Terminal value
        last_fcf = fcf
        tv_fcf = last_fcf * D(1 + terminal_g)
        tv = tv_fcf / D(wacc - terminal_g)
        tv_pv = tv / (D(1 + wacc) ** a.forecast_years)

        ev = pv_fcf + tv_pv
        equity = ev - D(a.net_debt)
        per_share = ddiv(equity, D(a.shares_outstanding))

        return float(per_share)


# ─── Synthetic Peers ────────────────────────────────────────────────────────


@dataclass
class PeerComponent:
    """合成对标的组成部分"""

    name: str
    weight: float  # 业务权重 [0, 1]
    pe_ratio: float
    pb_ratio: float = 0.0
    ps_ratio: float = 0.0
    ev_ebitda: float = 0.0
    growth_rate: float = 0.0
    margin: float = 0.0


@dataclass
class SyntheticPeerAssumptions:
    """合成对标假设"""

    ticker: str
    company_name: str
    components: List[PeerComponent] = field(default_factory=list)
    company_eps: float = 0.0
    company_bvps: float = 0.0
    company_revenue_per_share: float = 0.0
    company_ebitda_per_share: float = 0.0

    def __post_init__(self):
        # 归一化权重
        total_weight = sum(c.weight for c in self.components)
        if total_weight > 0:
            for c in self.components:
                c.weight /= total_weight


@dataclass
class SyntheticPeerResult:
    """合成对标结果"""

    synthetic_pe: float = 0.0
    synthetic_pb: float = 0.0
    synthetic_ps: float = 0.0
    synthetic_ev_ebitda: float = 0.0
    implied_prices: Dict[str, float] = field(default_factory=dict)
    target_price: float = 0.0
    confidence: str = "medium"
    warnings: List[str] = field(default_factory=list)


class SyntheticPeerEngine:
    """合成对标引擎"""

    def __init__(self, assumptions: SyntheticPeerAssumptions):
        self.a = assumptions

    def run(self) -> SyntheticPeerResult:
        result = SyntheticPeerResult()
        a = self.a

        if not a.components:
            result.warnings.append("无对标组成部分")
            return result

        # 加权合成倍数
        total_weight = sum(c.weight for c in a.components)

        # PE
        pe_values = [(c.weight, c.pe_ratio) for c in a.components if c.pe_ratio > 0]
        if pe_values:
            result.synthetic_pe = sum(w * p for w, p in pe_values) / sum(w for w, _ in pe_values)
            if a.company_eps > 0:
                result.implied_prices["PE"] = a.company_eps * result.synthetic_pe

        # PB
        pb_values = [(c.weight, c.pb_ratio) for c in a.components if c.pb_ratio > 0]
        if pb_values:
            result.synthetic_pb = sum(w * p for w, p in pb_values) / sum(w for w, _ in pb_values)
            if a.company_bvps > 0:
                result.implied_prices["PB"] = a.company_bvps * result.synthetic_pb

        # PS
        ps_values = [(c.weight, c.ps_ratio) for c in a.components if c.ps_ratio > 0]
        if ps_values:
            result.synthetic_ps = sum(w * p for w, p in ps_values) / sum(w for w, _ in ps_values)
            if a.company_revenue_per_share > 0:
                result.implied_prices["PS"] = a.company_revenue_per_share * result.synthetic_ps

        # EV/EBITDA
        ev_values = [(c.weight, c.ev_ebitda) for c in a.components if c.ev_ebitda > 0]
        if ev_values:
            result.synthetic_ev_ebitda = sum(w * p for w, p in ev_values) / sum(w for w, _ in ev_values)
            if a.company_ebitda_per_share > 0:
                result.implied_prices["EV/EBITDA"] = a.company_ebitda_per_share * result.synthetic_ev_ebitda

        # 综合目标价
        prices = list(result.implied_prices.values())
        if prices:
            result.target_price = sum(prices) / len(prices)
        else:
            result.confidence = "low"
            result.warnings.append("无足够数据计算目标价")

        return result
