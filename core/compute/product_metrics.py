"""product_metrics.py — 产品运营数据（2026-08-08 非上市 PE/VC）

顶级 VC 成长期硬道理（权重15%）：用户增长/留存/转化/ARR/NDR。
本引擎评估产品运营健康度。

用法：
  from core.compute.product_metrics import ProductMetrics, build_prompt
  r = ProductMetrics(users=10000, growth=0.15, retention_30=0.4, arr=500000, ndr=1.1, ltv=3000, cac=500)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("2hao.product_metrics")


@dataclass
class ProductMetrics:
    users: float = 0  # 月活/用户数
    growth: float = 0.05  # 月增速
    retention_30: float = 0.2  # 30日留存
    arr: float = 0  # 年经常性收入
    ndr: float = 1.0  # 净收入留存率
    ltv: float = 0  # 客户生命周期价值
    cac: float = 0  # 获客成本

    def health(self) -> float:
        """产品健康度 0-1（多指标加权）。"""
        score = 0.0
        # 留存（权重高）
        score += min(self.retention_30 / 0.6, 1.0) * 0.3
        # 增速
        score += min(self.growth / 0.2, 1.0) * 0.2
        # NDR
        score += min(max(self.ndr - 0.8, 0) / 0.4, 1.0) * 0.2
        # LTV/CAC（>3 优秀）
        if self.cac > 0:
            ratio = self.ltv / self.cac
            score += min(ratio / 3.0, 1.0) * 0.3
        else:
            score += 0.5 * 0.3
        return round(score, 2)

    def verdict(self) -> str:
        h = self.health()
        if h >= 0.7:
            return "产品数据优秀（PMF 信号强）"
        if h >= 0.4:
            return "产品数据中等，需优化短板"
        return "产品数据偏弱，PMF 未验证"


def build_prompt(r: ProductMetrics) -> str:
    ltv_cac = f"{r.ltv / r.cac:.1f}" if r.cac > 0 else "N/A"
    return (
        f"产品运营数据：用户{r.users:,.0f} 月增{r.growth:.0%} 30日留存{r.retention_30:.0%} "
        f"ARR{r.arr:,.0f} NDR{r.ndr:.0%} LTV/CAC={ltv_cac} → 健康度{r.health():.0%}（{r.verdict()}）"
    )
