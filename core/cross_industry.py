# -*- coding: utf-8 -*-
"""cross_industry.py — 跨行业类比引擎 v1（M-A13）。

通过"行业特征签名"四元组匹配历史类比案例：
  {增速区间, CR3集中度区间, 资本密集度, 技术迭代周期}

用法：写作 prompt 中自动注入"该行业当前类似 X 行业的 Y 年阶段"类比段，
帮助分析师从已研究过的行业中借鉴分析框架和结论。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_LIB_FILE = Path(__file__).resolve().parent.parent / "data" / "analogy_library.yaml"


@lru_cache(maxsize=1)
def _library() -> list[dict]:
    try:
        d = yaml.safe_load(_LIB_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _growth_bucket(growth: float | None) -> str:
    if growth is None:
        return "unknown"
    if growth > 30:
        return "高增长(>30%)"
    if growth > 10:
        return "中增长(10-30%)"
    if growth > 0:
        return "低增长(0-10%)"
    return "负增长"


def _concentration_bucket(cr3: float | None) -> str:
    if cr3 is None:
        return "unknown"
    if cr3 > 60:
        return "高集中(CR3>60%)"
    if cr3 > 30:
        return "中集中(CR3 30-60%)"
    return "分散(CR3<30%)"


def match(
    industry: str,
    growth_rate: float | None = None,
    cr3: float | None = None,
    capital_intensity: str | None = None,
    tech_cycle: str | None = None,
) -> list[dict]:
    """按特征签名匹配历史类比。

    Returns: [{analogy_industry, analogy_year, similarity, key_lesson, caveats}]
    """
    g_bucket = _growth_bucket(growth_rate)
    c_bucket = _concentration_bucket(cr3)
    results = []
    for case in _library():
        score = 0.0
        if case.get("industry") == industry:
            continue  # 不跟自己比
        if growth_rate is not None and case.get("growth_bucket") == g_bucket:
            score += 2.0
        if cr3 is not None and case.get("concentration_bucket") == c_bucket:
            score += 2.0
        if capital_intensity and case.get("capital_intensity") == capital_intensity:
            score += 1.5
        if tech_cycle and case.get("tech_cycle") == tech_cycle:
            score += 1.5
        # 关键词加分（行业上下游或技术相关）
        for kw in case.get("related_keywords", []):
            if kw.lower() in industry.lower():
                score += 0.5
        if score >= 2.0:
            results.append(
                {
                    "analogy_industry": case.get("industry", ""),
                    "analogy_period": case.get("period", ""),
                    "similarity_score": round(score, 1),
                    "key_lesson": case.get("key_lesson", ""),
                    "caveats": case.get("caveats", ""),
                    "matched_dimensions": int(score / 0.5),
                }
            )
    results.sort(key=lambda x: -x["similarity_score"])
    return results[:3]


def format_block(matches: list[dict], current_industry: str) -> str:
    if not matches:
        return ""
    lines = [f"## [跨行业类比] {current_industry}当前阶段的历史参照："]
    for m in matches:
        lines.append(
            f"\n### 类比：{m['analogy_industry']}（{m['analogy_period']}）"
            f"\n相似度: {m['similarity_score']} | 匹配维度: {m['matched_dimensions']}"
            f"\n关键教训: {m['key_lesson']}"
            f"\n注意事项: {m['caveats']}"
        )
    lines.append("\n> 使用指南：类比用于提供分析框架和风险预警，不可直接套用结论——需说明当前行业与类比行业的本质差异。")
    return "\n".join(lines)


def build_block(industry: str, **kwargs) -> str:
    """主入口：匹配 + 格式化。"""
    matches = match(industry, **kwargs)
    return format_block(matches, industry)
