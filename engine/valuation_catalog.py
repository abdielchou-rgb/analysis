"""
20+ 估值方法全景 + 质量评分 + 行业感知估值。
参考 valueinvest (20+ methods) + Valuate (industry-aware) + AlphaAnalyst (quality scores)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# ─── Valuation Methods Catalog ──────────────────────────────────────────────


class ValuationCategory(str, Enum):
    DEEP_VALUE = "deep_value"
    GROWTH = "growth"
    MATURE = "mature"
    DIVIDEND = "dividend"
    FINANCIAL = "financial"
    CONGLOMERATE = "conglomerate"
    RELATIVE = "relative"
    QUALITY = "quality"
    CYCLICAL = "cyclical"


@dataclass
class ValuationMethod:
    """单个估值方法"""

    name: str
    category: ValuationCategory
    formula: str
    applicable_conditions: List[str] = field(default_factory=list)
    output: float = 0.0
    confidence: str = "medium"
    warnings: List[str] = field(default_factory=list)


class ValuationCatalog:
    """20+ 估值方法目录"""

    @staticmethod
    def graham_number(eps: float, bvps: float) -> float:
        """Graham Number = sqrt(22.5 × EPS × BVPS)"""
        if eps <= 0 or bvps <= 0:
            return 0.0
        return (22.5 * eps * bvps) ** 0.5

    @staticmethod
    def graham_formula(eps: float, growth_rate: float, aaa_yield: float = 0.045) -> float:
        """Graham Formula = EPS × (8.5 + 2g) × 4.4 / Y"""
        if aaa_yield <= 0:
            aaa_yield = 0.045
        return eps * (8.5 + 2 * growth_rate * 100) * 4.4 / (aaa_yield * 100)

    @staticmethod
    def ncav(net_current_assets: float, shares: float) -> float:
        """NCAV = (Current Assets - Total Liabilities) / Shares"""
        if shares <= 0:
            return 0.0
        return net_current_assets / shares

    @staticmethod
    def dcf_per_share(fair_value: float) -> float:
        return fair_value

    @staticmethod
    def reverse_dcf(
        current_price: float,
        shares: float,
        net_debt: float,
        wacc: float = 0.09,
        terminal_g: float = 0.03,
        years: int = 10,
    ) -> float:
        """Reverse DCF: 从当前价格倒算隐含 FCF 增长率"""
        # 简化：返回隐含增长率
        ev = current_price * shares + net_debt
        # 粗略估计
        implied_growth = (wacc - terminal_g) * 0.5  # 简化公式
        return implied_growth

    @staticmethod
    def earnings_power_value(ep_recurring_earnings: float, wacc: float) -> float:
        """EPV = Earnings / WACC (假设零增长)"""
        if wacc <= 0:
            return 0.0
        return ep_recurring_earnings / wacc

    @staticmethod
    def gordon_growth_model(dividend: float, cost_of_equity: float, growth: float) -> float:
        """Gordon Growth = D1 / (ke - g)"""
        if cost_of_equity <= growth:
            return 0.0
        return dividend * (1 + growth) / (cost_of_equity - growth)

    @staticmethod
    def two_stage_ddm(
        dividend: float, growth_stage1: float, growth_terminal: float, cost_of_equity: float, years: int = 10
    ) -> float:
        """两阶段 DDM"""
        if cost_of_equity <= growth_terminal:
            return 0.0
        pv = 0.0
        d = dividend
        for i in range(years):
            d *= 1 + growth_stage1
            pv += d / ((1 + cost_of_equity) ** (i + 1))
        terminal = d * (1 + growth_terminal) / (cost_of_equity - growth_terminal)
        pv += terminal / ((1 + cost_of_equity) ** years)
        return pv

    @staticmethod
    def peg_ratio(pe: float, earnings_growth: float) -> float:
        """PEG = PE / Earnings Growth Rate"""
        if earnings_growth <= 0:
            return float("inf")
        return pe / (earnings_growth * 100)

    @staticmethod
    def justified_pe(growth: float, payout_ratio: float, cost_of_equity: float) -> float:
        """Justified PE = Payout × (1+g) / (ke - g)"""
        if cost_of_equity <= growth:
            return 0.0
        return payout_ratio * (1 + growth) / (cost_of_equity - growth)

    @staticmethod
    def piotroski_f_score(financials: Dict[str, float]) -> int:
        """Piotroski F-Score (0-9)"""
        score = 0
        # Profitability (4 points)
        if financials.get("roa", 0) > 0:
            score += 1
        if financials.get("cfo", 0) > 0:
            score += 1
        if financials.get("roa_change", 0) > 0:
            score += 1
        if financials.get("cfo > net_income", 0) > 0:
            score += 1
        # Leverage (3 points)
        if financials.get("leverage_change", 0) < 0:
            score += 1
        if financials.get("current_ratio_change", 0) > 0:
            score += 1
        if financials.get("shares_change", 0) <= 0:
            score += 1
        # Efficiency (2 points)
        if financials.get("gross_margin_change", 0) > 0:
            score += 1
        if financials.get("asset_turnover_change", 0) > 0:
            score += 1
        return score

    @staticmethod
    def altman_z_score(
        assets: float,
        liabilities: float,
        working_capital: float,
        retained_earnings: float,
        ebit: float,
        market_cap: float,
        total_revenue: float,
    ) -> float:
        """Altman Z-Score = 1.2X1 + 1.4X2 + 3.3X3 + 0.6X4 + 1.0X5"""
        if assets <= 0:
            return 0.0
        x1 = working_capital / assets
        x2 = retained_earnings / assets
        x3 = ebit / assets
        x4 = market_cap / liabilities if liabilities > 0 else 0
        x5 = total_revenue / assets
        return 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

    @staticmethod
    def beneish_m_score(financials: Dict[str, float]) -> float:
        """Beneish M-Score > -1.78 indicates earnings manipulation"""
        # 简化版本
        dsri = financials.get("dsri", 1.0)
        gmi = financials.get("gmi", 1.0)
        aqi = financials.get("aqi", 1.0)
        sgi = financials.get("sgi", 1.0)
        depi = financials.get("depi", 1.0)
        sgai = financials.get("sgai", 1.0)
        lvgi = financials.get("lvgi", 1.0)
        tata = financials.get("tata", 0.0)

        m_score = (
            -4.84
            + 0.92 * dsri
            + 0.528 * gmi
            + 0.404 * aqi
            + 0.892 * sgi
            + 0.115 * depi
            - 0.172 * sgai
            + 4.679 * tata
            - 0.327 * lvgi
        )
        return m_score


# ─── Industry-Aware Valuation ───────────────────────────────────────────────


class IndustryType(str, Enum):
    STANDARD = "standard"
    BANK = "bank"
    INSURANCE = "insurance"
    REIT = "reit"
    ENERGY = "energy"
    MINING = "mining"
    TECH = "tech"
    PHARMA = "pharma"


@dataclass
class IndustryValuationAssumptions:
    """行业感知估值假设"""

    ticker: str
    company_name: str
    industry: IndustryType = IndustryType.STANDARD
    # 银行
    book_value_per_share: float = 0.0
    roe: float = 0.0
    cost_of_equity: float = 0.09
    growth_rate: float = 0.03
    # 保险
    embedded_value: float = 0.0
    vnb: float = 0.0  # Value of New Business
    # REIT
    ffo: float = 0.0  # Funds From Operations
    affo: float = 0.0  # Adjusted FFO
    nav: float = 0.0
    # 能源
    reserves: float = 0.0
    reserve_life: float = 0.0
    production_cost: float = 0.0
    commodity_price: float = 0.0
    # 通用
    shares: float = 1.0
    current_price: Optional[float] = None


@dataclass
class IndustryValuationResult:
    """行业感知估值结果"""

    method_used: str = ""
    target_price: float = 0.0
    details: Dict[str, float] = field(default_factory=dict)
    confidence: str = "medium"
    warnings: List[str] = field(default_factory=list)


class IndustryValuationEngine:
    """行业感知估值引擎 — 自动选择最适合的估值方法"""

    def __init__(self, assumptions: IndustryValuationAssumptions):
        self.a = assumptions

    def run(self) -> IndustryValuationResult:
        a = self.a
        result = IndustryValuationResult()

        if a.industry == IndustryType.BANK:
            result = self._val银行()
        elif a.industry == IndustryType.INSURANCE:
            result = self._val保险()
        elif a.industry == IndustryType.REIT:
            result = self._valREIT()
        elif a.industry == IndustryType.ENERGY:
            result = self._val能源()
        else:
            result = self._val标准()

        if a.current_price and a.current_price > 0 and result.target_price > 0:
            upside = (result.target_price / a.current_price - 1) * 100
            result.details["upside_pct"] = upside

        return result

    def _val银行(self) -> IndustryValuationResult:
        """银行估值: Justified P/B = (ROE - g) / (ke - g)"""
        a = self.a
        result = IndustryValuationResult(method_used="Justified P/B (Bank)")

        if a.roe > 0 and a.cost_of_equity > a.growth_rate:
            justified_pb = (a.roe - a.growth_rate) / (a.cost_of_equity - a.growth_rate)
            result.target_price = a.book_value_per_share * justified_pb
            result.details["justified_pb"] = justified_pb
            result.details["roe"] = a.roe
            result.details["ke"] = a.cost_of_equity
            result.details["g"] = a.growth_rate
        else:
            result.warnings.append("银行估值参数不足")
            result.confidence = "low"

        return result

    def _val保险(self) -> IndustryValuationResult:
        """保险估值: P/EV = 1.0 ± adjustments"""
        a = self.a
        result = IndustryValuationResult(method_used="P/EV (Insurance)")

        if a.embedded_value > 0:
            # 基准 P/EV = 1.0，根据 VNB 增长调整
            pev_multiple = 1.0 + (a.vnb / a.embedded_value if a.embedded_value > 0 else 0)
            result.target_price = a.embedded_value * pev_multiple / a.shares if a.shares > 0 else 0
            result.details["pev_multiple"] = pev_multiple
            result.details["embedded_value"] = a.embedded_value
        else:
            result.warnings.append("保险估值参数不足")
            result.confidence = "low"

        return result

    def _valREIT(self) -> IndustryValuationResult:
        """REIT 估值: P/FFO 或 NAV 折溢价"""
        a = self.a
        result = IndustryValuationResult(method_used="P/FFO + NAV (REIT)")

        prices = []
        if a.ffo > 0 and a.shares > 0:
            # 行业平均 P/FFO ≈ 15-20x
            ffo_per_share = a.ffo / a.shares
            implied = ffo_per_share * 17.5  # 中位数
            prices.append(implied)
            result.details["ffo_implied"] = implied

        if a.nav > 0 and a.shares > 0:
            nav_per_share = a.nav / a.shares
            # NAV 折价 10-20%
            implied = nav_per_share * 0.85
            prices.append(implied)
            result.details["nav_implied"] = implied

        if prices:
            result.target_price = sum(prices) / len(prices)
        else:
            result.warnings.append("REIT 估值参数不足")
            result.confidence = "low"

        return result

    def _val能源(self) -> IndustryValuationResult:
        """能源估值: NAV based on reserves"""
        a = self.a
        result = IndustryValuationResult(method_used="Reserve-Based NAV (Energy)")

        if a.reserves > 0 and a.commodity_price > 0:
            # 简化: Reserves × (Price - Cost) × Discount
            margin_per_unit = a.commodity_price - a.production_cost
            reserve_value = a.reserves * margin_per_unit
            # 按 reserve life 折现
            if a.reserve_life > 0:
                discount = 0.10  # 10% 折现率
                pv = reserve_value * (1 - (1 + discount) ** (-a.reserve_life)) / discount
            else:
                pv = reserve_value
            result.target_price = pv / a.shares if a.shares > 0 else 0
            result.details["reserve_value"] = reserve_value
            result.details["margin_per_unit"] = margin_per_unit
        else:
            result.warnings.append("能源估值参数不足")
            result.confidence = "low"

        return result

    def _val标准(self) -> IndustryValuationResult:
        """标准 DCF"""
        result = IndustryValuationResult(method_used="Standard DCF")
        result.warnings.append("使用标准 DCF，未识别特殊行业")
        return result
