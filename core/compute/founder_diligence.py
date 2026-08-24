"""founder_diligence.py — 创始人尽调（2026-08-08 非上市 PE/VC）

顶级 VC：投的是人（权重最高 20%）。创始人四维评分：背景/能力/动机/诚信。

用法：
  from core.compute.founder_diligence import FounderDiligence, build_prompt
  r = FounderDiligence(background=8, capability=7, motivation=9, integrity=6)
  # 各 0-10 分
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("2hao.founder")


@dataclass
class FounderDiligence:
    background: float = 5.0  # 行业经验/连续创业
    capability: float = 5.0  # 领导力/学习力/执行力
    motivation: float = 5.0  # 创业动机/融资目的
    integrity: float = 5.0  # 诚信/历史/关联交易
    notes: str = ""

    def score(self) -> float:
        """四维加权评分（0-10）。诚信权重最高（一票否决）。"""
        w = {"background": 0.25, "capability": 0.25, "motivation": 0.2, "integrity": 0.3}
        s = (
            self.background * w["background"]
            + self.capability * w["capability"]
            + self.motivation * w["motivation"]
            + self.integrity * w["integrity"]
        )
        return round(s, 1)

    def verdict(self) -> str:
        s = self.score()
        if self.integrity < 4:
            return "一票否决：诚信风险高，不投"
        if s >= 7.5:
            return "创始人优秀，可推进"
        if s >= 5.5:
            return "创始人合格，需补强短板"
        return "创始人偏弱，谨慎"


def build_prompt(r: FounderDiligence) -> str:
    return (
        f"创始人尽调四维评分：背景{r.background}/能力{r.capability}/"
        f"动机{r.motivation}/诚信{r.integrity} → 综合 {r.score()}/10（{r.verdict()}）"
        + (f"；备注：{r.notes}" if r.notes else "")
    )
