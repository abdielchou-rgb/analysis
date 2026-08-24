"""多因子归因（量/价/结构/汇率）— 回答增长从哪来"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AttributionResult:
    volume_effect: float = 0
    price_effect: float = 0
    mix_effect: float = 0
    fx_effect: float = 0
    total_growth: float = 0
    volume_pct: float = 0
    price_pct: float = 0


class RevenueAttribution:
    """营收增长的多因子归因。"""

    def __init__(self, q0, q1, p0, p1, offshore_ratio=0, fx_change=0):
        self.q0, self.q1 = q0, q1
        self.p0, self.p1 = p0, p1
        self.offshore_ratio = offshore_ratio
        self.fx_change = fx_change

    def decompose(self) -> AttributionResult:
        v = (self.q1 - self.q0) * self.p0
        p = self.q0 * (self.p1 - self.p0)
        m = (self.q1 - self.q0) * (self.p1 - self.p0)
        t = self.q1 * self.p1 - self.q0 * self.p0
        return AttributionResult(
            volume_effect=round(v, 2),
            price_effect=round(p, 2),
            mix_effect=round(m, 2),
            total_growth=round(t, 2),
            volume_pct=round(v / max(t, 1) * 100, 1) if t else 0,
            price_pct=round(p / max(t, 1) * 100, 1) if t else 0,
        )
