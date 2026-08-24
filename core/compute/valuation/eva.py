"""EVA (Economic Value Added) / 经济利润模型 — 超越会计净利润，衡量真实价值创造

EVA = NOPAT - (Invested Capital x WACC)
如果 > 0 → 创造价值
如果 < 0 → 毁灭价值

用法：
  from core.compute.valuation.eva import EVAModel, AltmanZScore
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EVAResult:
    eva: float
    nopat: float
    invested_capital: float
    wacc_pct: float
    capital_charge: float
    eva_margin_pct: float
    verdict: str


class EVAModel:
    """EVA/经济利润 — 衡量真实价值创造。"""

    def __init__(self, nopat: float, invested_capital: float, wacc: float = 0.10):
        self.nopat = nopat
        self.invested_capital = invested_capital
        self.wacc = wacc

    def calculate(self) -> EVAResult:
        charge = self.invested_capital * self.wacc
        eva = self.nopat - charge
        verdict = "创造价值" if eva > 0 else ("毁灭价值" if eva < 0 else "持平")
        return EVAResult(
            eva=round(eva, 0),
            nopat=self.nopat,
            invested_capital=self.invested_capital,
            wacc_pct=self.wacc * 100,
            capital_charge=round(charge, 0),
            eva_margin_pct=round(eva / max(self.nopat, 1) * 100, 2) if self.nopat else 0,
            verdict=verdict,
        )


class AltmanZScore:
    """Altman Z-Score 破产预警模型 (制造业版)"""

    def __init__(
        self,
        working_capital: float,
        retained_earnings: float,
        ebit: float,
        market_cap: float,
        total_assets: float,
        total_liabilities: float,
        revenue: float,
    ):
        self.wc = working_capital
        self.re = retained_earnings
        self.ebit = ebit
        self.mcap = market_cap
        self.ta = total_assets
        self.tl = total_liabilities
        self.rev = revenue

    def calculate(self) -> dict:
        ta = max(self.ta, 1)
        x1 = self.wc / ta
        x2 = self.re / ta
        x3 = self.ebit / ta
        x4 = self.mcap / max(self.tl, 1)
        x5 = self.rev / ta
        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
        if z < 1.81:
            zone = "危险区（Distress Zone）- 破产风险高"
        elif z < 2.99:
            zone = "灰色区（Grey Zone）- 需警惕"
        else:
            zone = "安全区（Safe Zone）- 破产风险低"
        return {
            "z_score": round(z, 2),
            "zone": zone,
            "x1": round(x1, 4),
            "x2": round(x2, 4),
            "x3": round(x3, 4),
            "x4": round(x4, 4),
            "x5": round(x5, 4),
        }
