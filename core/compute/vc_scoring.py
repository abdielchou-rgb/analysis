"""vc_scoring.py — PE/VC 十大维度打分引擎（2026-08-08 非上市）

对齐红杉/高瓴/IDG 等顶级 VC 十大评估维度权重：
  市场20% / 痛点15% / 商业模式15% / 团队20% / 产品数据15%
  壁垒10% / 融资估值5% / 退出5% / 风险3% / 呈现2%

用法：
  from core.compute.vc_scoring import vc_score, build_prompt
  r = vc_score({...})  # 每维 0-10
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.vc_scoring")

# 十大维度权重
DIMENSIONS = [
    ("market", "市场空间", 0.20),
    ("pain", "痛点方案", 0.15),
    ("business_model", "商业模式", 0.15),
    ("team", "团队", 0.20),
    ("product", "产品数据", 0.15),
    ("moat", "竞争壁垒", 0.10),
    ("valuation", "融资估值", 0.05),
    ("exit", "退出路径", 0.05),
    ("risk", "风险应对", 0.03),
    ("presentation", "呈现质量", 0.02),
]


@dataclass
class VcScoreResult:
    scores: dict = field(default_factory=dict)
    weighted: float = 0.0
    verdict: str = ""
    details: list = field(default_factory=list)


def vc_score(scores: dict) -> VcScoreResult:
    """十大维度加权评分。

    scores: {维度key: 0-10 分}。缺省按 5 分。
    """
    r = VcScoreResult()
    total = 0.0
    for key, name, weight in DIMENSIONS:
        s = float(scores.get(key, 5.0))
        s = max(0.0, min(10.0, s))
        r.scores[key] = s
        total += s * weight
        r.details.append((name, s, weight))
    r.weighted = round(total, 2)

    # 判定
    if r.weighted >= 7.5:
        r.verdict = "强烈推荐（A类项目）"
    elif r.weighted >= 6.0:
        r.verdict = "推荐（B类项目，补短板后可投）"
    elif r.weighted >= 4.5:
        r.verdict = "观望（C类项目，需重大改进）"
    else:
        r.verdict = "不投（D类项目）"

    # 一票否决：团队<4 或市场<4
    if r.scores.get("team", 5) < 4:
        r.verdict += "（团队否决）"
    if r.scores.get("market", 5) < 4:
        r.verdict += "（市场否决）"
    return r


def build_prompt(r: VcScoreResult) -> str:
    lines = ["=== PE/VC 十大维度评分 ==="]
    for name, s, w in r.details:
        lines.append(f"- {name}（权重{w:.0%}）: {s:.1f}/10")
    lines.append(f"综合评分: {r.weighted:.2f}/10（{r.verdict}）")
    lines.append("=== 评分结束 ===")
    return "\n".join(lines)
