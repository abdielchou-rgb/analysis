# -*- coding: utf-8 -*-
"""H: research_planner v1 — 研究阶段规划器（零 LLM，确定性）。

P3-B 落地：把"冲突检测"从 Gate（事后）前移到研究阶段（事前）。
输入 enrich 后的 collected_data：
  1. 问题树：SAC 维度 × 模板 → 每维 2 条必答问题
  2. 冲突扫描：复用 data_caliber.detect_value_conflicts
  3. 追问查询：对每个冲突生成定向补采查询串

LLM 驱动的深版（多视角模拟对话）为 Phase C 项；本 v1 提供确定性骨架。
"""

from __future__ import annotations

_QUESTION_TEMPLATES = [
    # (中文关键词, [英文别名], [两问])
    (
        "规模",
        ["market", "sizing", "tam"],
        ["该市场规模的口径（全球/中国/细分）与年份是什么？", "规模数字的来源与测算方法是否可复核？"],
    ),
    ("增速", ["growth", "cagr"], ["增速是同比还是复合？基年是什么？", "增速与量价拆分是否自洽？"]),
    ("毛利率", ["margin"], ["毛利率变化的主因是价格、成本结构还是产品组合？", "与可比公司同口径毛利率差异多少？"]),
    ("竞争", ["competitive", "peer", "player"], ["主要玩家的份额与变化方向？", "竞争要素是价格、技术还是渠道？"]),
    (
        "估值",
        ["valuation", "dcf", "pe"],
        ["估值锚（EPS/PE/DCF 假设）分别是什么？", "多方法结论是否一致，分歧来自哪个假设？"],
    ),
]


def question_tree(dims: list[str]) -> list[dict]:
    """每维度 → 必答问题（中英文关键词命中 2 条；未命中共用通用 2 问）。"""
    tree = []
    for dim in dims or []:
        d = str(dim).lower()
        qs = []
        for kw, aliases, pair in _QUESTION_TEMPLATES:
            hay = f"{d} {kw}"
            if any(a.lower() in d for a in aliases) or kw in d or any(a in hay for a in aliases):
                qs.extend(pair)
                break
        if not qs:
            qs = [f"{dim}：当前事实与数据支撑是什么？", f"{dim}：市场共识与本报告的分歧点在哪？"]
        tree.append({"dim": dim, "questions": qs[:2]})
    return tree


def detect_conflicts(collected_data: dict) -> list[dict]:
    """数据层冲突前移检测（复用 data_caliber）。"""
    try:
        from core.data_caliber import detect_value_conflicts

        dd = collected_data.get("data_dict") if isinstance(collected_data, dict) else None
        if not dd:
            # 兜底：从 chart_data 展平一级数值
            cd = (collected_data or {}).get("chart_data", {}) or {}
            dd = {}
            for k, v in cd.items():
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        if isinstance(vv, (int, float)):
                            dd[f"{k}_{kk}"] = vv
        return detect_value_conflicts(dd) if dd else []
    except Exception:
        return []


def followup_queries(conflicts: list[dict], asset: str) -> list[str]:
    """每个冲突生成一条定向仲裁查询。"""
    # 最多 5 条，控制采集成本
    qs = []
    for c in (conflicts or [])[:5]:
        ind = c.get("indicator", "")
        entries = c.get("entries") or []
        keys = "/".join(str(e.get("key", "")) for e in entries[:2])
        qs.append(f"{asset} {ind} 权威口径 核实（{keys}）")
    return qs


def plan(asset: str, dims: list[str], collected_data: dict) -> dict:
    conflicts = detect_conflicts(collected_data)
    return {
        "question_tree": question_tree(dims),
        "conflicts": conflicts,
        "followup_queries": followup_queries(conflicts, asset),
        "n_conflicts": len(conflicts),
    }
