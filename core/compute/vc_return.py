"""vc_return.py — VC 回报模型（2026-08-08 非上市 PE/VC）

顶级 PE/VC 拍板依据：投入×稀释×终局估值×概率 → MOIC/IRR。

  MOIC = 退出价值×稀释后持股 / 投入
  IRR  = 从投入到退出的年化回报

用法：
  from core.compute.vc_return import VcReturnModel, build_prompt
  r = VcReturnModel(invest=1000, exit_value=50000, dilution=0.15, years=5, exit_prob=0.3)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("2hao.vc_return")


@dataclass
class VcReturnModel:
    invest: float = 0  # 本轮投入（万）
    exit_value: float = 0  # 退出估值（万）
    dilution: float = 0.1  # 稀释后持股比例（0-1）
    years: float = 5  # 持有年限
    exit_prob: float = 0.5  # 退出概率（0-1）

    def moic(self) -> float:
        """回报倍数。"""
        if self.invest <= 0:
            return 0.0
        exit_proceeds = self.exit_value * self.dilution
        return round(exit_proceeds / self.invest, 2)

    def irr(self) -> float:
        """年化 IRR。"""
        m = self.moic()
        if m <= 0:
            return 0.0
        return round(m ** (1 / self.years) - 1, 4)

    def risk_adjusted_moic(self) -> float:
        """概率调整回报。"""
        return round(self.moic() * self.exit_prob, 2)

    def verdict(self) -> str:
        m = self.moic()
        ram = self.risk_adjusted_moic()
        if m >= 10 and self.exit_prob >= 0.3:
            return f"回报优秀（MOIC {m:.1f}x），可投"
        if m >= 5:
            return f"回报良好（MOIC {m:.1f}x），建议推进"
        if ram >= 1:
            return f"风险调整后回报 >1（{ram:.1f}x），勉强可投"
        return f"回报不足（MOIC {m:.1f}x，风险调整后{ram:.1f}x），不投"


def build_prompt(r: VcReturnModel) -> str:
    return (
        f"VC 回报模型：投入{r.invest:,.0f}万 × 稀释后持股{r.dilution:.0%} × 退出估值{r.exit_value:,.0f}万 "
        f"× 退出概率{r.exit_prob:.0%} → MOIC {r.moic():.1f}x / IRR {r.irr():.1%} / "
        f"风险调整MOIC {r.risk_adjusted_moic():.1f}x（{r.verdict()}）"
    )
