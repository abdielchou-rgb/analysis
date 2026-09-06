"""
Intent → Research 接线（Phase E，2026-09-06）。

把 engine/intent_engine.py 的 MECEIssueTree（假设 → 数据需求 → 证伪条件）
接进生产采集规划：
1. decompose() 产出假设树
2. data_needs 映射到采集能力矩阵（现有 data_collector 能采/不能采）
3. 采不到的假设 → 报告"未验证声明"清单（诚实留白）
4. 新增 gate 检查 hypothesis_coverage 的数据源

用法（research_planner / data 节点）：
    from core.intent_bridge import build_hypothesis_plan
    plan = build_hypothesis_plan(asset, report_type, collected_data)
    → {"hypotheses": [...], "unverifiable": [...], "coverage": float}
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

logger = logging.getLogger("2hao.intent_bridge")

# ── 采集能力矩阵（data_collector 现有能力 → 可支撑的数据需求） ──────────

COLLECTION_CAPABILITY = {
    "revenue_growth": {"fig_revenue_trend", "akshare_annual"},
    "margin_expansion": {"fig_profitability", "akshare_annual"},
    "valuation": {"fig_valuation", "price", "market_cap"},
    "competition": {"fig_industry_board", "peers", "web_search"},
    "business_model": {"web_search", "tavily"},
    "risk_policy": {"web_search", "tavily"},
    "management": {"web_search", "tavily"},
    "moat": {"web_search", "knowledge_base"},
    "capital_flow": {"fig_capital_flow", "stock_sdk"},
    "segments": {"fig_business_segments", "akshare_zygc"},
}

# 假设树 node_type → 数据需求关键词
_NODE_NEED_KEYWORDS = {
    "revenue_growth": ("增长", "营收", "收入", "销量"),
    "margin_expansion": ("毛利", "利润率", "盈利"),
    "valuation": ("估值", "目标价", "市值"),
    "competition": ("竞争", "份额", "对手", "格局"),
    "business_model": ("商业模式", "变现", "渠道"),
    "risk_policy": ("政策", "风险", "监管"),
    "management": ("管理", "治理", "团队"),
    "moat": ("壁垒", "护城河", "优势"),
    "capital_flow": ("资金", "流向", "主力"),
    "segments": ("分部", "业务构成", "占比"),
}


def _classify_need(need_text: str) -> str | None:
    t = str(need_text)
    for cap, kws in _NODE_NEED_KEYWORDS.items():
        if any(k in t for k in kws):
            return cap
    return None


def _has_capability(collected_data: dict, cap: str) -> bool:
    """该数据需求是否已被采集（chart_data/数据 dict 有对应键）。"""
    cd = collected_data.get("chart_data") if isinstance(collected_data, dict) else None
    cd = cd or {}
    if not isinstance(cd, dict):
        return False
    key_map = COLLECTION_CAPABILITY.get(cap, set())
    has = any(k in cd for k in key_map if k.startswith("fig_"))
    # web_search/tavily/knowledge 类：collected_data 有 text/news 即算
    if not has:
        for src in key_map:
            if src in ("web_search", "tavily") and (
                collected_data.get("text") or collected_data.get("news") or collected_data.get("research_text")
            ):
                has = True
                break
            if src == "knowledge_base" and collected_data.get("knowledge"):
                has = True
                break
    return has


def build_hypothesis_plan(
    asset: str,
    report_type: str,
    collected_data: dict,
    persona: str = "equity_research",
) -> dict:
    """主入口：MECE 假设树 → 采集覆盖矩阵 → 未验证清单。"""
    try:
        from engine.intent_engine import DecisionPersona, MECEIssueTree
    except ImportError as e:
        logger.warning("intent_engine 不可用: %s", e)
        return {"status": "unavailable", "hypotheses": [], "unverifiable": [], "coverage": None}

    try:
        _persona = DecisionPersona(persona)
    except ValueError:
        _persona = DecisionPersona.EQUITY_RESEARCH

    tree = MECEIssueTree(f"{asset} 价值分析", {"biz_model": "revenue_growth"})
    root = tree.decompose()

    hypotheses, unverifiable, covered = [], [], 0
    for hyp in root.children:  # 顶层假设
        hyp_record = {
            "hypothesis": hyp.label[:120],
            "data_needs": [],
            "falsifiers": [c.label[:80] for c in hyp.children if c.node_type.value == "falsifier"],
            "supported": None,
        }
        need_caps = []
        for child in hyp.children:
            if child.node_type.value == "data_need":
                cap = _classify_need(child.label)
                if cap:
                    need_caps.append(cap)
                    hyp_record["data_needs"].append(
                        {"need": child.label[:80], "capability": cap, "collected": _has_capability(collected_data, cap)}
                    )
        if not hyp_record["data_needs"]:
            hyp_record["supported"] = None  # 无可判定需求
            unverifiable.append(hyp_record)
        else:
            collected_n = sum(1 for d in hyp_record["data_needs"] if d["collected"])
            hyp_record["supported"] = collected_n == len(hyp_record["data_needs"])
            if hyp_record["supported"]:
                covered += 1
            else:
                unverifiable.append(hyp_record)
        hypotheses.append(hyp_record)

    total_hyp = len(hypotheses)
    coverage = covered / total_hyp if total_hyp else None
    return {
        "status": "ok",
        "asset": asset,
        "persona": _persona.value,
        "hypotheses": hypotheses,
        "unverifiable": unverifiable,
        "coverage": round(coverage, 4) if coverage is not None else None,
    }


def format_unverifiable_appendix(plan: dict) -> str:
    """未验证假设 → 报告"认知边界"附录块。"""
    if not plan or plan.get("status") != "ok" or not plan.get("unverifiable"):
        return ""
    lines = ["### 认知边界（未验证假设，诚实留白）", ""]
    for h in plan["unverifiable"][:6]:
        lines.append(
            f"- 假设『{h['hypothesis']}』：数据需求未采集（{', '.join(d['capability'] for d in h['data_needs'] if not d['collected'])[:60]}），本报告未验证该判断"
        )
    lines.append("")
    lines.append("以上假设在后续数据补采后验证；引用本报告结论时请注意该边界。")
    return "\n".join(lines)
