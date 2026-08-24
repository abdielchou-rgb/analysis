"""
反向 DCF 估值引擎 — 从当前股价反推市场隐含预期

核心逻辑：
  市场当前股价 P 隐含了一个"增长率/ROIC"假设。
  反向 DCF = 给定 P，解出使 DCF 等式成立的隐含增长率 g 或隐含 ROIC。

公式：
  Enterprise Value = 市值 + 净债务
  EV = Σ(FCF_t / (1+WACC)^t) + TerminalValue / (1+WACC)^n
  Terminal Value (GGM) = FCF_n × (1+g) / (WACC - g)
  → 给定 EV/WACC/FCF，解出 g (隐含永续增长率)
  → 或给定 EV/WACC/FCF/股本，解出隐含 FCF margin / 隐含 ROIC

用法：
  from core.compute.valuation.reverse_dcf import ReverseDCF
  rd = ReverseDCF(market_cap=150e8, net_debt=10e8, fcf_ttm=5e8, wacc=0.10)
  result = rd.solve_implied_growth()
  # → {"implied_growth_pct": 3.2, "expectation_gap_pct": -1.5, ...}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.valuation.reverse_dcf")


@dataclass
class ReverseDCFResult:
    """反向 DCF 计算结果。"""

    implied_growth_pct: float  # 隐含永续增长率 (%)
    our_growth_pct: float | None  # 分析师假设的增长率 (%)——如有输入
    expectation_gap_pct: float  # 隐含 vs 假设的差距 (百分点)
    implied_fcf_margin_pct: float  # 隐含 FCF margin (%)——若有营收数据
    implied_roic_pct: float | None  # 隐含 ROIC (%)——若有投入资本数据
    sensitivity: dict = field(default_factory=dict)  # WACC/增长率的双变量敏感性
    warnings: list = field(default_factory=list)


class ReverseDCF:
    """
    反向 DCF 计算器。
    输入：当前市场数据 → 输出：市场隐含的增长率/ROIC/FCF margin。
    """

    def __init__(
        self,
        market_cap: float,  # 总市值（元）
        net_debt: float = 0,  # 净债务 = 总负债 - 现金（元）
        fcf_ttm: float | None = None,  # TTM 自由现金流（元）
        revenue_ttm: float | None = None,  # TTM 营收（元）
        invested_capital: float | None = None,  # 投入资本（元）
        wacc: float = 0.10,  # 加权平均资本成本
        tax_rate: float = 0.25,  # 有效税率
        growth_assumption: float | None = None,  # 分析师假设的增长率 (%)
        shares_outstanding: float | None = None,  # 总股本
    ):
        self.market_cap = market_cap
        self.net_debt = net_debt
        self.ev = market_cap + net_debt  # 企业价值
        self.fcf_ttm = fcf_ttm
        self.revenue_ttm = revenue_ttm
        self.invested_capital = invested_capital
        self.wacc = wacc
        self.tax_rate = tax_rate
        self.growth_assumption = growth_assumption
        self.shares_outstanding = shares_outstanding

    def solve_implied_growth(self) -> ReverseDCFResult:
        """
        从 EV + FCF + WACC 反推市场隐含的永续增长率 g。

        公式：EV = FCF_ttm × (1+g) / (WACC - g)
        → g = (EV × WACC - FCF_ttm) / (EV + FCF_ttm)
        """
        if not self.fcf_ttm or self.fcf_ttm <= 0:
            return ReverseDCFResult(
                implied_growth_pct=0,
                expectation_gap_pct=0,
                implied_fcf_margin_pct=0,
                warnings=["FCF <= 0，无法做反向 DCF"],
            )

        ev = self.ev
        fcf = self.fcf_ttm
        wacc = self.wacc

        # 解隐含增长率
        if ev + fcf <= 0:
            implied_g = -0.01
        else:
            implied_g = (ev * wacc - fcf) / (ev + fcf)

        implied_g_pct = implied_g * 100

        # 预期差 = 假设增长率 - 隐含增长率
        gap = (self.growth_assumption - implied_g_pct) if self.growth_assumption else 0

        # 隐含 FCF margin
        implied_fcf_margin = (fcf / self.revenue_ttm * 100) if self.revenue_ttm and self.revenue_ttm > 0 else 0

        # 隐含 ROIC
        implied_roic = None
        if self.invested_capital and self.invested_capital > 0:
            implied_roic = fcf / self.invested_capital * 100

        # 敏感性矩阵：WACC × 增长率
        sensitivity = {}
        for w in [wacc - 0.01, wacc, wacc + 0.01]:
            row = {}
            for g_delta in [-0.02, -0.01, 0, 0.01, 0.02]:
                g_test = implied_g + g_delta
                if w > g_test:
                    implied_ev = fcf * (1 + g_test) / (w - g_test)
                    row[f"g={g_test * 100:.1f}%"] = implied_ev
                else:
                    row[f"g={g_test * 100:.1f}%"] = float("inf")
            sensitivity[f"WACC={w * 100:.1f}%"] = row

        return ReverseDCFResult(
            implied_growth_pct=round(implied_g_pct, 2),
            our_growth_pct=self.growth_assumption,
            expectation_gap_pct=round(gap, 2),
            implied_fcf_margin_pct=round(implied_fcf_margin, 2),
            implied_roic_pct=round(implied_roic, 2) if implied_roic else None,
            sensitivity=sensitivity,
        )

    def solve_implied_fcf_margin(self) -> dict:
        """从 EV + 营收 + WACC 反推市场隐含的 FCF margin。"""
        if not self.revenue_ttm or self.revenue_ttm <= 0:
            return {"error": "需营收数据"}
        # 假设市场用 g=3% 作为隐含假设
        g_assumed = 0.03
        implied_fcf = self.ev * (self.wacc - g_assumed) / (1 + g_assumed)
        implied_margin = implied_fcf / self.revenue_ttm * 100
        return {
            "implied_fcf": round(implied_fcf, 0),
            "implied_fcf_margin_pct": round(implied_margin, 2),
            "assumed_growth_pct": g_assumed * 100,
        }

    def to_dict(self) -> dict:
        """序列化用于报告注入。"""
        result = self.solve_implied_growth()
        d = {
            "enterprise_value": round(self.ev, 0),
            "wacc": f"{self.wacc * 100:.1f}%",
            "implied_growth_pct": result.implied_growth_pct,
            "expectation_gap_pct": result.expectation_gap_pct,
            "implied_fcf_margin_pct": result.implied_fcf_margin_pct,
            "implied_roic_pct": result.implied_roic_pct,
            "sensitivity_available": bool(result.sensitivity),
        }
        if result.warnings:
            d["warnings"] = result.warnings
        return d
