"""Dupont 分解 / ROE 驱动因子拆解 — 最基本的财务诊断工具

ROE = 净利率 × 资产周转率 × 权益乘数
核心问题："ROE 变动是来自利润率改善、周转率提升、还是杠杆变化？"

用法：
  from core.compute.financial.dupont import DupontAnalysis
  da = DupontAnalysis(net_profit=10, revenue=100, total_assets=200, equity=120)
  da.decompose()
  # → {"net_margin": 10%, "asset_turnover": 0.5, "equity_multiplier": 1.67, "roe": 8.3%}
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DupontResult:
    net_margin_pct: float
    asset_turnover: float
    equity_multiplier: float
    roe_pct: float
    components: dict


class DupontAnalysis:
    def __init__(self, net_profit: float, revenue: float, total_assets: float, equity: float):
        self.net_profit = net_profit
        self.revenue = revenue
        self.total_assets = total_assets
        self.equity = equity

    def decompose(self) -> DupontResult:
        net_margin = self.net_profit / self.revenue if self.revenue else 0
        turnover = self.revenue / self.total_assets if self.total_assets else 0
        multiplier = self.total_assets / self.equity if self.equity else 0
        roe = net_margin * turnover * multiplier
        return DupontResult(
            net_margin_pct=round(net_margin * 100, 2),
            asset_turnover=round(turnover, 4),
            equity_multiplier=round(multiplier, 4),
            roe_pct=round(roe * 100, 2),
            components={
                "net_margin": f"{net_margin * 100:.2f}%",
                "asset_turnover": f"{turnover:.4f}",
                "equity_multiplier": f"{multiplier:.4f}",
                "formula": "净利率 × 周转率 × 杠杆 = ROE",
            },
        )
