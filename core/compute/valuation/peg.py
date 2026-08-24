"""PEG 估值框架 — 成长股核心估值工具

PEG = PE / 预期增速
  < 1.0 → 低估（增速覆盖估值）
  1.0 ~ 1.5 → 合理
  > 1.5 → 高估（估值溢价需增速兑现支撑）

用法：
  from core.compute.valuation.peg import PEGValuation
  peg = PEGValuation(pe=25, growth_pct=20)
  peg.ratio  # → 1.25
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PEGResult:
    peg_ratio: float
    pe: float
    growth_pct: float
    valuation_label: str  # 低估/合理/高估
    implied_growth: float  # 从 PE 反推的隐含增速


class PEGValuation:
    def __init__(self, pe: float, growth_pct: float, industry_peg: float = None):
        self.pe = pe
        self.growth_pct = growth_pct
        self.industry_peg = industry_peg

    @property
    def ratio(self) -> float:
        if self.growth_pct <= 0:
            return float("inf")
        return self.pe / self.growth_pct

    @property
    def implied_growth(self) -> float:
        """从 PE 反推市场隐含增速 (假设 PEG=1 为合理)。"""
        return self.pe  # PEG=1 → 增速 = PE

    def analyze(self) -> PEGResult:
        r = self.ratio
        if r < 0.8:
            label = "低估"
        elif r < 1.2:
            label = "合理"
        elif r < 1.5:
            label = "偏高"
        else:
            label = "高估"
        return PEGResult(
            peg_ratio=round(r, 2),
            pe=self.pe,
            growth_pct=self.growth_pct,
            valuation_label=label,
            implied_growth=self.implied_growth,
        )
