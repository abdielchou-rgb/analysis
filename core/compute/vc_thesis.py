# -*- coding: utf-8 -*-
"""vc_thesis.py — 投资论题（2026-08-08 非上市 PE/VC 差额补足）

顶级 VC 第一问：为什么这家公司能赢？
  1. 论题假设（3-5 条"我们相信X"）
  2. 证伪条件（什么数据会推翻论题）
  3. 独特性（为什么不是别人）

用法：
  from core.compute.vc_thesis import VcThesis, build_thesis_prompt
  t = VcThesis([
    ("市场规模", "我们相信全球X市场到2030年达Y亿", "若增速低于Z则证伪"),
  ])
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.vc_thesis")


@dataclass
class Thesis:
    name: str
    belief: str       # 我们相信X
    falsify: str      # 什么数据会推翻
    strength: float = 0.5  # 0-1 论题强度（信心）


@dataclass
class VcThesisResult:
    theses: list = field(default_factory=list)
    avg_strength: float = 0.0
    weakest: str = ""
    verdict: str = ""


def build_thesis(theses: list) -> VcThesisResult:
    """构建投资论题。

    theses: [{name, belief, falsify, strength}]
    """
    r = VcThesisResult()
    r.theses = [Thesis(**t) for t in theses]
    if r.theses:
        r.avg_strength = round(sum(t.strength for t in r.theses) / len(r.theses), 2)
        r.weakest = min(r.theses, key=lambda t: t.strength).name
        if r.avg_strength >= 0.7:
            r.verdict = "论题整体成立（可推进尽调）"
        elif r.avg_strength >= 0.4:
            r.verdict = f"论题部分成立，最弱论题『{r.weakest}』需验证"
        else:
            r.verdict = f"论题偏弱，最强依赖『{r.weakest}』需重写"
    return r


def build_prompt(r: VcThesisResult) -> str:
    lines = ["=== 投资论题（为什么赢 + 证伪条件）==="]
    for t in r.theses:
        lines.append(f"- [{t.strength:.0%}] {t.name}: {t.belief}")
        lines.append(f"  · 证伪条件: {t.falsify}")
    lines.append(f"综合论题强度: {r.avg_strength:.0%}（{r.verdict}）")
    lines.append("=== 论题结束 ===")
    return "\n".join(lines)
