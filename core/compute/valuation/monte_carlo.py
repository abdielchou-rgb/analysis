"""
Monte Carlo 概率估值引擎 — 从单点数到概率分布

核心逻辑：
  给定关键假设的概率分布（WACC/FCF/增长率），
  运行 N 次蒙特卡洛模拟，输出估值的概率分布/分位数/VaR。

用法：
  from core.compute.valuation.monte_carlo import MonteCarloValuation
  mc = MonteCarloValuation(wacc_mean=0.10, wacc_std=0.01,
                           fcf_mean=5e8, fcf_std=0.5e8)
  result = mc.simulate(n=10000)
  # → {"mean_ev": ..., "p10": ..., "p90": ..., "var_95": ...}
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger("2hao.valuation.monte_carlo")


@dataclass
class MCResult:
    n_simulations: int
    mean_ev: float
    median_ev: float
    p10_ev: float
    p90_ev: float
    var_95: float  # 95% VaR (左尾 5%)
    downside_prob: float  # 估值低于某个阈值的概率
    values: list = field(default_factory=list)


class MonteCarloValuation:
    def __init__(self, wacc_mean: float, wacc_std: float,
                 fcf_mean: float, fcf_std: float,
                 growth_mean: float = 0.03, growth_std: float = 0.01,
                 terminal_growth: float = 0.03,
                 net_debt: float = 0, seed: int = 42):
        self.wacc_mean = wacc_mean
        self.wacc_std = wacc_std
        self.fcf_mean = fcf_mean
        self.fcf_std = fcf_std
        self.growth_mean = growth_mean
        self.growth_std = growth_std
        self.terminal_growth = terminal_growth
        self.net_debt = net_debt
        np.random.seed(seed)

    def simulate(self, n: int = 10000, threshold: float = 0) -> MCResult:
        waccs = np.random.normal(self.wacc_mean, self.wacc_std, n)
        fcfs = np.random.normal(self.fcf_mean, self.fcf_std, n)
        growths = np.random.normal(self.growth_mean, self.growth_std, n)

        evs = []
        for i in range(n):
            w = max(waccs[i], 0.02)  # WACC >= 2%
            fcf = max(fcfs[i], 0)
            g = growths[i]
            if w > g:
                terminal = fcf * (1 + self.terminal_growth) / (w - self.terminal_growth)
                ev = fcf + terminal - self.net_debt
            else:
                ev = float("inf")
            evs.append(ev)

        evs = np.array([e for e in evs if e != float("inf")])
        if len(evs) == 0:
            return MCResult(
                n_simulations=n, mean_ev=0, median_ev=0,
                p10_ev=0, p90_ev=0, var_95=0, downside_prob=1.0,
            )

        return MCResult(
            n_simulations=n,
            mean_ev=round(float(np.mean(evs)), 0),
            median_ev=round(float(np.median(evs)), 0),
            p10_ev=round(float(np.percentile(evs, 10)), 0),
            p90_ev=round(float(np.percentile(evs, 90)), 0),
            var_95=round(float(np.percentile(evs, 5)), 0),
            downside_prob=round(float(np.mean(evs < threshold)), 4) if threshold > 0 else 0,
            values=evs[:100].tolist(),
        )

    def to_report(self) -> str:
        r = self.simulate()
        return (f"Monte Carlo 估值分布（{r.n_simulations}次模拟）:\n"
                f"  均值: {r.mean_ev:.0f} | 中位: {r.median_ev:.0f}\n"
                f"  P10: {r.p10_ev:.0f} | P90: {r.p90_ev:.0f}\n"
                f"  95% VaR: {r.var_95:.0f}（95%概率估值不低于此值）")