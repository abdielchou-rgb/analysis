# -*- coding: utf-8 -*-
"""H: research_planner v2 — 研究阶段规划器（LLM 智能问题生成 + 确定性冲突检测）。

v2 升级：问题树从模板匹配升级为 LLM 生成——每维度产出资产专属、
挑战共识的非显性研究问题。LLM 不可用时回退 v1 模板。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("2hao.research_planner")


# ── v1 模板（回退用）──────────────────────────────────────────

_QUESTION_TEMPLATES = [
    (
        "规模",
        ["market", "sizing", "tam"],
        [
            "该市场规模的口径（全球/中国/细分）与年份是什么？",
            "规模数字的来源与测算方法是否可复核？",
        ],
    ),
    (
        "增速",
        ["growth", "cagr"],
        [
            "增速是同比还是复合？基年是什么？",
            "增速与量价拆分是否自洽？",
        ],
    ),
    (
        "毛利率",
        ["margin"],
        [
            "毛利率变化的主因是价格、成本结构还是产品组合？",
            "与可比公司同口径毛利率差异多少？",
        ],
    ),
    (
        "竞争",
        ["competitive", "peer", "player"],
        [
            "主要玩家的份额与变化方向？",
            "竞争要素是价格、技术还是渠道？",
        ],
    ),
    (
        "估值",
        ["valuation", "dcf", "pe"],
        [
            "估值锚（EPS/PE/DCF 假设）分别是什么？",
            "多方法结论是否一致，分歧来自哪个假设？",
        ],
    ),
]


def question_tree(dims: list[str]) -> list[dict]:
    """v1 模板版。"""
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


# ── v2 LLM 问题生成 ──────────────────────────────────────────

_LLM_QUESTION_PROMPT = """你是顶级卖方研究所的资深分析师。针对{asset}，为分析维度「{dim}」生成 2 个具体、非共识、可验证的研究问题。

要求：
1. 问题必须针对该公司的具体情况，不能是通用模板
2. 问题应挑战市场一致预期，寻找预期差
3. 问题必须可用公开数据验证
4. 每个问题应导向一个可操作的投资洞察

输出格式：恰好两行，每行一个问题，不要编号，不要解释。"""


def _llm_generate_questions(
    asset: str,
    dim: str,
    report_type: str,
    data_context: dict,
) -> list[str] | None:
    """调用 LLM 为单维度生成研究问题。失败返回 None。"""
    try:
        from core.deepseek_client import call_deepseek

        # 注入数据上下文摘要帮助 LLM 生成更精准的问题
        cd_keys = []
        chart_data = (data_context or {}).get("chart_data", {}) or {}
        for k in sorted(chart_data.keys())[:8]:
            cd_keys.append(k)

        prompt = _LLM_QUESTION_PROMPT.format(asset=asset, dim=dim)
        if cd_keys:
            prompt += f"\n\n可用数据键：{', '.join(cd_keys)}"

        r = call_deepseek(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        content = r["choices"][0]["message"]["content"].strip()
        lines = [l.strip().lstrip("0123456789.、） ") for l in content.split("\n") if l.strip() and len(l.strip()) > 10]
        return lines[:2] if len(lines) >= 2 else None
    except Exception as e:
        logger.debug("[RQ-LLM] %s", str(e)[:60])
        return None


def question_tree_v2(
    dims: list[str],
    asset: str = "",
    report_type: str = "",
    data_context: dict | None = None,
    use_llm: bool = True,
) -> list[dict]:
    """v2 问题树：优先 LLM 生成，回退 v1 模板。

    use_llm=False 或 LLM 失败时自动降级到模板版。
    """
    # 骨架模式或无 LLM key → 直接走模板
    import os

    if not use_llm or not os.environ.get("DEEPSEEK_API_KEY"):
        return question_tree(dims)

    tree = []
    dc = data_context or {}

    def _process_dim(dim):
        """为单个维度生成问题（供并行调用）"""
        llm_qs = _llm_generate_questions(asset, dim, report_type, dc)
        if llm_qs:
            return {"dim": dim, "questions": llm_qs, "source": "llm"}
        fallback = question_tree([dim])
        if fallback:
            return fallback[0]
        return {
            "dim": dim,
            "questions": [
                f"{dim}：当前事实与数据支撑是什么？",
                f"{dim}：市场共识与本报告的分歧点在哪？",
            ],
        }

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_process_dim, dim): dim for dim in (dims or [])}
        for fut in as_completed(futures):
            tree.append(fut.result())

    return tree


# ── 冲突检测（不变） ─────────────────────────────────────────


def detect_conflicts(collected_data: dict) -> list[dict]:
    try:
        from core.data_caliber import detect_value_conflicts

        dd = collected_data.get("data_dict") if isinstance(collected_data, dict) else None
        if not dd:
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
    qs = []
    for c in (conflicts or [])[:5]:
        ind = c.get("indicator", "")
        entries = c.get("entries") or []
        keys = "/".join(str(e.get("key", "")) for e in entries[:2])
        qs.append(f"{asset} {ind} 权威口径 核实（{keys}）")
    return qs


# ── 主入口 ───────────────────────────────────────────────────


def plan(
    asset: str,
    dims: list[str],
    collected_data: dict,
    report_type: str = "",
    use_llm: bool = True,
) -> dict:
    """研究规划主入口。use_llm=True 时尝试 LLM 生成问题（成本可控）。"""
    conflicts = detect_conflicts(collected_data)
    qt = question_tree_v2(dims, asset, report_type, collected_data, use_llm)
    return {
        "question_tree": qt,
        "conflicts": conflicts,
        "followup_queries": followup_queries(conflicts, asset),
        "n_conflicts": len(conflicts),
        "llm_generated": any(n.get("source") == "llm" for n in qt),
    }
