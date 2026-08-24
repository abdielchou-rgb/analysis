#!/usr/bin/env python3
"""LBO 估值模型 — 杠杆收购分析（投行标准）

用途：并购/私有化场景的估值核心工具
公式：IRR = FCF yield + leverage effect + multiple expansion
       Exit EV = Exit EBITDA × Exit Multiple
       Equity Return = Exit EV - Net Debt
       IRR = (Equity Return / Initial Equity)^(1/years) - 1

用法：
  from core.compute.valuation.lbo import LBOModel
  lbo = LBOModel(entry_ebitda=100, entry_multiple=10, debt_pct=0.6)
  result = lbo.calculate()
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass
class LBOResult:
    entry_ev: float
    entry_equity: float
    exit_ev: float
    exit_equity: float
    irr_pct: float
    cash_roi_pct: float
    moic: float  # Multiple on Invested Capital


class LBOModel:
    """杠杆收购模型 — 标准投行 LBO 分析。"""

    def __init__(self, entry_ebitda: float, entry_multiple: float,
                 debt_pct: float = 0.6, exit_multiple: float = None,
                 ebitda_growth: float = 0.05, years: int = 5,
                 interest_rate: float = 0.05, debt_repay: float = 0.3):
        self.entry_ebitda = entry_ebitda
        self.entry_multiple = entry_multiple
        self.entry_ev = entry_ebitda * entry_multiple
        self.debt_pct = debt_pct
        self.exit_multiple = exit_multiple or entry_multiple
        self.ebitda_growth = ebitda_growth
        self.years = years
        self.interest_rate = interest_rate
        self.debt_repay = debt_repay
        self.exit_ebitda = entry_ebitda * (1 + ebitda_growth) ** years

    def calculate(self) -> LBOResult:
        entry_equity = self.entry_ev * (1 - self.debt_pct)
        exit_ev = self.exit_ebitda * self.exit_multiple
        initial_debt = self.entry_ev * self.debt_pct
        debt_remaining = initial_debt * (1 - self.debt_repay)
        # 简化：利息在 EBITDA 层面已覆盖（标准 LBO 假设）
        exit_equity = exit_ev - debt_remaining
        moic = exit_equity / max(entry_equity, 1)
        irr = (exit_equity / max(entry_equity, 1)) ** (1 / max(self.years, 1)) - 1
        cash_roi = (exit_equity - entry_equity) / max(entry_equity, 1) * 100
        return LBOResult(
            entry_ev=round(self.entry_ev, 0),
            entry_equity=round(entry_equity, 0),
            exit_ev=round(exit_ev, 0),
            exit_equity=round(exit_equity, 0),
            irr_pct=round(irr * 100, 2),
            cash_roi_pct=round(cash_roi, 1),
            moic=round(moic, 2),
        )

    def to_report(self) -> str:
        r = self.calculate()
        return (f"LBO 分析 ({self.years}年):\\n"
                f"  Entry EV: {r.entry_ev:.0f} | Exit EV: {r.exit_ev:.0f}\\n"
                f"  Entry Equity: {r.entry_equity:.0f} | Exit Equity: {r.exit_equity:.0f}\\n"
                f"  IRR: {r.irr_pct}% | MOIC: {r.moic}x | ROI: {r.cash_roi_pct}%")


if __name__ == "__main__":
    lbo = LBOModel(entry_ebitda=100, entry_multiple=10, debt_pct=0.6)
    r = lbo.calculate()
    print(f"LBO: IRR={r.irr_pct}%, MOIC={r.moic}x")