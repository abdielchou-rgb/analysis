"""
Monte Carlo 模拟引擎 — 带相关矩阵、Box-Muller 变换。
参考 valuation-project: 10,000 次模拟 ~3 秒，相关性保持。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class MonteCarloAssumptions:
    """Monte Carlo 模拟假设"""

    ticker: str
    company_name: str
    n_simulations: int = 10000
    seed: Optional[int] = None

    # 基础 DCF 参数
    base_revenue: float = 100.0
    revenue_growth_mean: float = 0.10
    revenue_growth_std: float = 0.03
    ebit_margin_mean: float = 0.15
    ebit_margin_std: float = 0.02
    wacc_mean: float = 0.09
    wacc_std: float = 0.01
    terminal_growth_mean: float = 0.03
    terminal_growth_std: float = 0.005
    da_pct_mean: float = 0.03
    capex_pct_mean: float = 0.04
    wc_pct_mean: float = 0.02
    tax_rate: float = 0.25
    forecast_years: int = 5
    net_debt: float = 0.0
    shares_outstanding: float = 1.0
    current_price: Optional[float] = None

    # 相关矩阵 (key1, key2) → correlation
    correlations: Dict[Tuple[str, str], float] = field(default_factory=dict)

    def __post_init__(self):
        if not self.correlations:
            self.correlations = {
                ("revenue_growth", "ebit_margin"): 0.3,
                ("revenue_growth", "wacc"): -0.2,
                ("ebit_margin", "wacc"): -0.1,
                ("wacc", "terminal_growth"): 0.4,
            }


@dataclass
class MonteCarloResult:
    """Monte Carlo 模拟结果"""

    fair_values: List[float] = field(default_factory=list)
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    p5: float = 0.0  # 5th percentile
    p25: float = 0.0
    p75: float = 0.0
    p95: float = 0.0
    prob_above_current: Optional[float] = None
    confidence_interval_80: Tuple[float, float] = (0.0, 0.0)
    confidence_interval_95: Tuple[float, float] = (0.0, 0.0)
    histogram: Dict[str, int] = field(default_factory=dict)
    sensitivity_ranking: List[Tuple[str, float]] = field(default_factory=list)


class BoxMullerTransform:
    """Box-Muller 正态分布变换"""

    @staticmethod
    def generate(n: int, mean: float = 0.0, std: float = 1.0, rng: random.Random = None) -> List[float]:
        if rng is None:
            rng = random.Random()
        results = []
        for _ in range(0, n, 2):
            u1 = rng.random()
            u2 = rng.random()
            z0 = math.sqrt(-2 * math.log(max(u1, 1e-10))) * math.cos(2 * math.pi * u2)
            z1 = math.sqrt(-2 * math.log(max(u2, 1e-10))) * math.sin(2 * math.pi * u2)
            results.append(mean + std * z0)
            if len(results) < n:
                results.append(mean + std * z1)
        return results[:n]


class CorrelationEngine:
    """相关性保持引擎 — Cholesky 分解"""

    @staticmethod
    def cholesky(corr_matrix: List[List[float]]) -> List[List[float]]:
        n = len(corr_matrix)
        L = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1):
                s = sum(L[i][k] * L[j][k] for k in range(j))
                if i == j:
                    L[i][j] = math.sqrt(max(corr_matrix[i][i] - s, 1e-10))
                else:
                    L[i][j] = (corr_matrix[i][j] - s) / max(L[j][j], 1e-10)
        return L

    @staticmethod
    def apply_correlation(
        independent_samples: List[List[float]],
        corr_matrix: List[List[float]],
    ) -> List[List[float]]:
        """对独立样本施加相关性"""
        n_vars = len(independent_samples)
        n_samples = len(independent_samples[0]) if independent_samples else 0

        L = CorrelationEngine.cholesky(corr_matrix)

        correlated = [[0.0] * n_samples for _ in range(n_vars)]
        for s in range(n_samples):
            z = [independent_samples[v][s] for v in range(n_vars)]
            for i in range(n_vars):
                for j in range(i + 1):
                    correlated[i][s] += L[i][j] * z[j]

        return correlated


class MonteCarloEngine:
    """Monte Carlo DCF 模拟引擎"""

    def __init__(self, assumptions: MonteCarloAssumptions):
        self.a = assumptions
        self.rng = random.Random(assumptions.seed)

    def run(self) -> MonteCarloResult:
        a = self.a
        n = a.n_simulations

        # 生成独立正态样本
        samples = {
            "revenue_growth": BoxMullerTransform.generate(n, a.revenue_growth_mean, a.revenue_growth_std, self.rng),
            "ebit_margin": BoxMullerTransform.generate(n, a.ebit_margin_mean, a.ebit_margin_std, self.rng),
            "wacc": BoxMullerTransform.generate(n, a.wacc_mean, a.wacc_std, self.rng),
            "terminal_growth": BoxMullerTransform.generate(n, a.terminal_growth_mean, a.terminal_growth_std, self.rng),
        }

        # 构建相关矩阵
        keys = ["revenue_growth", "ebit_margin", "wacc", "terminal_growth"]
        corr_matrix = [[1.0] * len(keys) for _ in range(len(keys))]
        for (k1, k2), corr in a.correlations.items():
            if k1 in keys and k2 in keys:
                i, j = keys.index(k1), keys.index(k2)
                corr_matrix[i][j] = corr
                corr_matrix[j][i] = corr

        # 施加相关性
        independent = [samples[k] for k in keys]
        correlated = CorrelationEngine.apply_correlation(independent, corr_matrix)
        for i, k in enumerate(keys):
            samples[k] = correlated[i]

        # 运行模拟
        fair_values = []
        sensitivities = {k: [] for k in keys}

        for i in range(n):
            growth = samples["revenue_growth"][i]
            margin = samples["ebit_margin"][i]
            wacc = samples["wacc"][i]
            tg = samples["terminal_growth"][i]

            # 确保 WACC > terminal growth
            if wacc <= tg:
                wacc = tg + 0.02

            fv = self._compute_dcf(growth, margin, wacc, tg)
            fair_values.append(fv)

            sensitivities["revenue_growth"].append(fv)
            sensitivities["ebit_margin"].append(fv)
            sensitivities["wacc"].append(fv)
            sensitivities["terminal_growth"].append(fv)

        # 统计结果
        result = MonteCarloResult(fair_values=fair_values)
        sorted_vals = sorted(fair_values)
        n_vals = len(sorted_vals)

        result.mean = sum(sorted_vals) / n_vals
        result.median = sorted_vals[n_vals // 2]
        result.std = math.sqrt(sum((v - result.mean) ** 2 for v in sorted_vals) / n_vals)
        result.p5 = sorted_vals[int(n_vals * 0.05)]
        result.p25 = sorted_vals[int(n_vals * 0.25)]
        result.p75 = sorted_vals[int(n_vals * 0.75)]
        result.p95 = sorted_vals[int(n_vals * 0.95)]
        result.confidence_interval_80 = (sorted_vals[int(n_vals * 0.10)], sorted_vals[int(n_vals * 0.90)])
        result.confidence_interval_95 = (result.p5, result.p95)

        if a.current_price and a.current_price > 0:
            above = sum(1 for v in fair_values if v > a.current_price)
            result.prob_above_current = above / n_vals

        # 直方图
        bins = 20
        min_val = sorted_vals[0]
        max_val = sorted_vals[-1]
        bin_width = (max_val - min_val) / bins
        for b in range(bins):
            low = min_val + b * bin_width
            high = low + bin_width
            count = sum(1 for v in sorted_vals if low <= v < high)
            result.histogram[f"{low:.0f}-{high:.0f}"] = count

        # 敏感性排序
        for key in keys:
            vals = sensitivities[key]
            if vals:
                var = sum((v - result.mean) ** 2 for v in vals) / len(vals)
                result.sensitivity_ranking.append((key, math.sqrt(var)))
        result.sensitivity_ranking.sort(key=lambda x: -x[1])

        return result

    def _compute_dcf(self, growth: float, margin: float, wacc: float, terminal_g: float) -> float:
        a = self.a
        curr_rev = a.base_revenue
        pv_fcf = 0.0

        for i in range(a.forecast_years):
            curr_rev *= 1 + growth
            ebit = curr_rev * margin
            da = curr_rev * a.da_pct_mean
            capex = curr_rev * a.capex_pct_mean
            wc = curr_rev * a.wc_pct_mean
            nopat = ebit * (1 - a.tax_rate)
            fcf = nopat + da - capex - wc
            pv_fcf += fcf / ((1 + wacc) ** (i + 1))

        tv_fcf = fcf * (1 + terminal_g)
        tv = tv_fcf / (wacc - terminal_g)
        tv_pv = tv / ((1 + wacc) ** a.forecast_years)

        ev = pv_fcf + tv_pv
        equity = ev - a.net_debt
        return equity / a.shares_outstanding
