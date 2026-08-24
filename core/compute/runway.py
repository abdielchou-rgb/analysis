"""runway.py — Runway 资金链（2026-08-08 非上市 PE/VC）

顶级 VC 风控：公司账上现金能撑多久？到里程碑要烧多少？何时融资？

  runway = 现金 / 月烧钱率
  融资需求 = 到下一里程碑的缺口

用法：
  from core.compute.runway import Runway, build_prompt
  r = Runway(cash=500, burn=50, milestone_cost=300, milestone_months=6)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("2hao.runway")


@dataclass
class Runway:
    cash: float = 0  # 账上现金（万）
    burn: float = 0  # 月烧钱率（万）
    milestone_cost: float = 0  # 到里程碑总需求（万）
    milestone_months: float = 0  # 到里程碑月数

    def months(self) -> float:
        """当前现金能撑月数。"""
        if self.burn <= 0:
            return 999.0
        return round(self.cash / self.burn, 1)

    def funding_gap(self) -> float:
        """到里程碑资金缺口。"""
        need = self.milestone_cost
        have = self.cash + (self.burn * max(self.milestone_months, 0)) * 0  # 现金
        # 简单：缺口 = 里程碑需求 - 当前现金（假设里程碑前还需持续烧钱）
        gap = self.milestone_cost - self.cash
        return round(max(gap, 0), 1)

    def verdict(self) -> str:
        m = self.months()
        if m >= 18:
            return f"Runway {m:.0f} 个月，资金充足（VC 偏好 18-24 月）"
        if m >= 9:
            return f"Runway {m:.0f} 个月，需在 6-12 个月内启动融资"
        return f"Runway 仅 {m:.0f} 个月，资金紧张，尽快融资"


def build_prompt(r: Runway) -> str:
    return (
        f"Runway 资金链：账上现金{r.cash:,.0f}万 / 月烧钱{r.burn:,.0f}万 → 可撑 {r.months():.0f} 个月；"
        f"到里程碑（{r.milestone_months:.0f}月）资金缺口 {r.funding_gap():,.0f}万（{r.verdict()}）"
    )
