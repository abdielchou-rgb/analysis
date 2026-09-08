# -*- coding: utf-8 -*-
"""H: research_planner v2 — 研究阶段规划器（LLM 智能问题生成 + 确定性冲突检测）。

v2 升级：问题树从模板匹配升级为 LLM 生成——每维度产出资产专属、
挑战共识的非显性研究问题。LLM 不可用时回退 v1 模板。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

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
            # 修复（2026-09-04）：此前缺省 provider="opencode_go"（未注册）→
            # 全量回退打 zhipu 加剧 429。research_planner 节点按路由策略走。
            provider="deepseek",
            timeout=30.0,  # P0-1a（2026-09-07）：单次调用 30s 独立超时，不靠共享预算兜底
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
    llm_budget_s: float | None = None,
) -> list[dict]:
    """v2 问题树：优先 LLM 生成，回退 v1 模板。

    use_llm=False 或 LLM 失败时自动降级到模板版。

    2026-09-07（真实 PROFILE 驱动）：新增 llm_budget_s 共享总预算——
    6 路并行下若各维度独立无限等 deepseek，单轮可达 155s 中位/20min max。
    超预算后未完成维度一律回落 v1 模板，绝不让单维度把整轮拖死。
    """
    import os
    import time as _time

    if llm_budget_s is None:
        try:
            from core.settings import research_llm_budget_s

            llm_budget_s = research_llm_budget_s()
        except Exception:
            llm_budget_s = 45.0

    # 骨架模式或无 LLM key → 直接走模板
    if not use_llm or not os.environ.get("DEEPSEEK_API_KEY"):
        return question_tree(dims)

    dc = data_context or {}
    tree: list[dict] = []
    _deadline = _time.monotonic() + max(5.0, float(llm_budget_s))

    def _template_for(dim: str) -> dict:
        fb = question_tree([dim])
        if fb:
            return fb[0]
        return {
            "dim": dim,
            "questions": [
                f"{dim}：当前事实与数据支撑是什么？",
                f"{dim}：市场共识与本报告的分歧点在哪？",
            ],
            "source": "template",
        }

    def _process_dim(dim):
        """为单个维度生成问题（供并行调用）——LLM 失败/异常即回落模板。"""
        if _time.monotonic() > _deadline:
            return _template_for(dim)  # 预算已尽，不再发起 LLM
        try:
            llm_qs = _llm_generate_questions(asset, dim, report_type, dc)
            if llm_qs:
                return {"dim": dim, "questions": llm_qs, "source": "llm"}
        except Exception as _e:
            logger.debug("[RQ] dim=%s LLM 异常回落模板: %s", dim, str(_e)[:60])
        return _template_for(dim)

    dims = list(dims or [])
    if not dims:
        return []

    from concurrent.futures import FIRST_COMPLETED, Future, wait

    pool = ThreadPoolExecutor(max_workers=min(6, len(dims)))
    futures: dict[Future, str] = {pool.submit(_process_dim, d): d for d in dims}
    pending = set(futures)
    try:
        # 预算有界等待：每轮只等"剩余预算"内最先完成的 future；
        # 预算耗尽即 break，主线程总等待 ≈ llm_budget_s（不让慢 LLM 拖死整轮）。
        while pending:
            remaining = _deadline - _time.monotonic()
            if remaining <= 0:
                break
            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            for fut in done:
                tree.append(fut.result())
        if pending:
            logger.warning(
                "[RQ] LLM 问题生成超总预算 %.1fs，%d 个维度回落 v1 模板",
                llm_budget_s,
                len(pending),
            )
            for f in pending:
                f.cancel()
    finally:
        # 关键：wait=False——已启动的慢线程在后台自行结束，不阻塞主流程。
        # 否则 `with` 的 shutdown(wait=True) 会让预算熔断形同虚设。
        pool.shutdown(wait=False, cancel_futures=True)

    # 补齐未完成维度（cancel 掉的 future 不会出现在 tree）
    _done_dims = {n.get("dim") for n in tree if isinstance(n, dict)}
    _fallback_count = 0
    for d in dims:
        if d not in _done_dims:
            tree.append(_template_for(d))
            _fallback_count += 1
    if _fallback_count:
        # P0-1a 观测指标：回落数量决定 30s 超时是否过紧
        logger.warning("[RQ] fallback_count=%d/%d（30s 超时+%.1fs 总预算）", _fallback_count, len(dims), llm_budget_s)

    # 保持原 dims 顺序（树结构确定性，便于测试/Gate）
    _by_dim = {n.get("dim"): n for n in tree if isinstance(n, dict)}
    return [_by_dim[d] for d in dims if d in _by_dim]


# ── 维度→MKB 条目映射（Evidence-Grounded Writing） ─────────────

# 每个维度 → 对 MKB 类别关键词（用于 select_entries 精准召回）
_DIM_MKB_KEYWORDS: dict[str, list[str]] = {
    "business_model": ["商业模式", "护城河", "竞争壁垒"],
    "financial_analysis": ["财务分析", "估值", "盈利", "毛利率", "ROE"],
    "competitive_position": ["竞争格局", "市场份额", "行业地位"],
    "growth_drivers": ["增长", "驱动力", "市场规模", "CAGR"],
    "governance_esg": ["治理", "ESG", "合规", "风险"],
    "valuation_assessment": ["估值", "DCF", "PE", "可比"],
    "catalyst": ["催化剂", "事件", "时间窗口"],
    "falsification": ["证伪", "风险", "反方"],
    "capital_flow": ["资金", "融资", "股东"],
    "core_disagreement": ["分歧", "预期差", "共识"],
    "decision_gate": ["决策", "投资", "建议"],
    "bold_call": ["预测", "判断", "观点"],
    "risk": ["风险", "威胁", "不确定性"],
    "market_sizing": ["市场规模", "TAM", "SAM"],
    "supply_chain": ["供应链", "产业链", "上游", "下游"],
    "policy": ["政策", "监管", "法规"],
    "trend": ["趋势", "技术路线", "演变"],
    "headline": ["业绩", "营收", "利润"],
    "key_surprise": ["超预期", "低于预期", " surprise"],
    "segment_analysis": ["分部", "业务拆分", "分业务"],
    "balance_cashflow": ["资产负债", "现金流", "负债率"],
    "outlook_implication": ["展望", "指引", "预期"],
}


def _build_dim_kb_map(
    dims: list[str],
    asset: str,
    report_type: str,
) -> dict[str, list[dict]]:
    """为每个维度预检索 MKB 条目，返回 {dim_id: [entry, ...]}。

    Evidence-Grounded Writing 基础设施：writer 按维度过滤注入，
    而不是全量盲注。select_entries 是纯打分排序（无 LLM），延迟可忽略。
    """
    try:
        from core.methodology_kb import select_entries

        dim_map: dict[str, list[dict]] = {}
        for dim in dims:
            kw = _DIM_MKB_KEYWORDS.get(dim, [dim])
            keywords = [asset] + kw
            entries = select_entries(keywords, report_type, max_items=3)
            if entries:
                dim_map[dim] = entries
        return dim_map
    except Exception:
        return {}


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
    # Evidence-Grounded Writing：为每个维度预检索 MKB 条目
    dim_kb_map = _build_dim_kb_map(dims, asset, report_type)
    return {
        "question_tree": qt,
        "conflicts": conflicts,
        "followup_queries": followup_queries(conflicts, asset),
        "n_conflicts": len(conflicts),
        "llm_generated": any(n.get("source") == "llm" for n in qt),
        "dim_kb_map": dim_kb_map,
    }
