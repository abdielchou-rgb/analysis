"""实物期权估值 — 技术公司/研发密集行业必须

核心逻辑：
  DCF/NPV 低估了有灵活性的资产价值。
  实物期权 = 项目价值 = NPV + 期权价值(灵活性溢价)

适用场景：
  - 研发管线：放弃/延迟/扩张期权
  - 矿产/能源：开采/停产期权
  - 专利/IP：独家使用权期权

用法：
  from core.compute.valuation.real_option import RealOption
  ro = RealOption(underlying=100, strike=80, volatility=0.3, years=3, rate=0.05)
  ro.black_scholes()
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class RealOptionResult:
    name: str
    option_value: float
    npv: float
    total_value: float
    parameters: dict


class RealOption:
    """实物期权估值 — Black-Scholes 框架。"""

    def __init__(self, underlying: float, strike: float, volatility: float, years: float, rate: float = 0.05):
        self.S = underlying
        self.K = strike
        self.v = volatility
        self.T = years
        self.r = rate

    def _d1(self) -> float:
        return math.log(self.S / self.K) + (self.r + 0.5 * self.v**2) * self.T

    def _d2(self) -> float:
        return self._d1() - self.v * math.sqrt(self.T)

    @staticmethod
    def _N(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def black_scholes(self) -> dict:
        if self.T <= 0 or self.v <= 0:
            return {"option_value": 0}
        d1 = self._d1()
        d2 = self._d2()
        call = self.S * self._N(d1) - self.K * math.exp(-self.r * self.T) * self._N(d2)
        return {"option_value": round(call, 2), "d1": round(d1, 4), "d2": round(d2, 4)}

    def expansion_option(self, npv: float) -> RealOptionResult:
        """扩张期权。"""
        bs = self.black_scholes()
        return RealOptionResult(
            name="扩张期权",
            option_value=bs["option_value"],
            npv=npv,
            total_value=npv + bs["option_value"],
            parameters={"S": self.S, "K": self.K, "v": self.v},
        )

    def to_report(self) -> str:
        bs = self.black_scholes()
        return (
            f"实物期权估值:\n  BS 期权价值: {bs['option_value']:.2f}\n"
            f"  标的={self.S} 执行价={self.K} 波动率={self.v:.0%}\n"
            f"  期限={self.T}年 无风险利率={self.r:.1%}"
        )
