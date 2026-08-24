"""cap_table.py — 资本结构分析（2026-08-08 非上市 PE/VC）

顶级 PE 决策：cap table / 优先股 / 清算优先权 / 稀释。
  1. Cap table：创始人/团队/机构/期权池 各占多少
  2. 优先股条款：清算优先倍数 / 参与权
  3. 稀释后创始人控制权

用法：
  from core.compute.cap_table import CapTable, build_prompt
  ct = CapTable(founder=0.6, team=0.1, investors=0.25, option_pool=0.05,
                liquidation_multiple=1.0, participation=True)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("2hao.cap_table")


@dataclass
class CapTable:
    founder: float = 0.6  # 创始人持股
    team: float = 0.1  # 团队/员工
    investors: float = 0.25  # 机构
    option_pool: float = 0.05  # 期权池
    liquidation_multiple: float = 1.0  # 清算优先倍数
    participation: bool = False  # 是否参与分红（参与优先股）

    def control_risk(self) -> float:
        """创始人控制风险 0-1。"""
        if self.founder < 0.3:
            return 0.8
        if self.founder < 0.5:
            return 0.5
        return 0.2

    def investor_terms(self) -> str:
        """优先股条款评估。"""
        terms = []
        if self.liquidation_multiple > 1.0:
            terms.append(f"清算优先{self.liquidation_multiple:.1f}x（对创始人不友好）")
        else:
            terms.append("清算优先1x（标准）")
        if self.participation:
            terms.append("参与优先股（投资人双重获益）")
        else:
            terms.append("非参与优先股（标准）")
        return "；".join(terms)

    def verdict(self) -> str:
        r = self.control_risk()
        if r >= 0.7:
            return f"创始人控制风险高（持股{self.founder:.0%}），需关注"
        if r >= 0.4:
            return f"创始人控制中等（持股{self.founder:.0%}），需一致行动安排"
        return f"创始人控制良好（持股{self.founder:.0%}）"


def build_prompt(ct: CapTable) -> str:
    return (
        f"Cap table：创始人{ct.founder:.0%} 团队{ct.team:.0%} 机构{ct.investors:.0%} "
        f"期权池{ct.option_pool:.0%}；{ct.investor_terms()} → 控制风险{ct.control_risk():.0%}（{ct.verdict()}）"
    )
