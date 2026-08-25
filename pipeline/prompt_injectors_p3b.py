# -*- coding: utf-8 -*-
"""P3-B 追加注入器（方法论置信度 / [E#] 证据清单 / 研究问题树）。

与 prompt_injectors.py 同契约：纯函数 `(ctx) -> str`。
在此独立成文件以便增量演进；注册仍集中在 prompt_injectors.INJECTORS。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("2hao.injectors.p3b")


def _inj_mc_str(ctx):
    """P3-B：方法论置信度先验（预测账本 → prompt）。无已验证历史则空。"""
    try:
        from core.methodology_confidence import confidence_block

        return confidence_block(asset=ctx.get("asset", ""))
    except Exception as e:
        logger.debug("[MC] %s", e)
    return ""


def _inj_ev_str(ctx):
    """P3-B：[E#] 证据清单——写作期引用绑定的地基。

    把 chart_data 的 fig_* 键编成编号清单注入 prompt，要求关键数字标注
    [E#]；validate 侧 _check_inline_citations 以 warning 校验标注密度。
    """
    try:
        cd = (ctx.get("data_context") or {}).get("chart_data", {}) or {}
        rows = []
        for k in sorted(cd.keys()):
            if not str(k).startswith("fig_"):
                continue
            preview = str(cd[k])[:80]
            rows.append(f"[E{len(rows) + 1}] {k} = {preview}")
        if len(rows) < 3:
            return ""
        head = "## [证据编号清单] 关键数字请标注对应证据编号 [En]；未列入清单的关键数字必须给出具体来源：\n"
        return head + "\n".join(rows[:40])
    except Exception as e:
        logger.debug("[EV] %s", e)
    return ""


def _inj_rp_str(ctx):
    """P3-B：研究规划注入器——必答问题 + 冲突追问。

    从 collected_data 的 _research_questions/_followup_queries 读取，
    生成研究阶段必须覆盖的问题清单块。
    """
    dc = ctx.get("data_context") or {}
    rqs = dc.get("_research_questions") or []
    fq = dc.get("_followup_queries") or []
    if not rqs and not fq:
        return ""
    lines = ["## [研究必答问题] 写作时须逐条回应以下研究问题："]
    for i, q in enumerate(rqs[:15], 1):
        lines.append(f"  {i}. {q}")
    if fq:
        lines.append("\n## [数据冲突追问] 以下口径冲突需在正文中显式解释或补充来源：")
        for j, q in enumerate(fq, 1):
            lines.append(f"  {j}. {q}")
    return "\n".join(lines)


def _inj_kb_str(ctx):
    """K-07：知识库 RAG 注入器——按资产名+报告类型检索相关知识段落。

    零 LLM：纯 FTS5 全文匹配，按 BM25 相关度排序取 top-5。
    无索引时自动构建；无命中时返回空串。
    """
    try:
        from core.knowledge_base import ensure_index, search

        ensure_index()
        asset = ctx.get("asset", "")
        report_type = ctx.get("report_type", "")
        # 构建查询：资产名 + 报告类型中文名
        query_parts = []
        if asset:
            query_parts.append(asset)
        type_kw = {
            "listed_company": "公司研究",
            "industry_deep": "行业研究",
            "unlisted_company": "私募股权",
            "earnings_notes": "业绩点评",
            "decision_memo": "决策备忘录",
        }.get(report_type, "行业研究")
        query_parts.append(type_kw)
        # 加一个通用方法论词提高召回
        query_parts.append("估值")

        results = search(" ".join(query_parts), top_k=5)
        if not results:
            return ""
        lines = ["## [知识库参考] 以下段落来自内部知识库（券商研报/方法论），供分析框架参考："]
        for i, r in enumerate(results, 1):
            src = r["source"].replace("\\", "/").split("/")[-1].replace(".md", "")
            snippet = r["snippet"][:200]
            lines.append(f"\n[KB{i}] 来源: {src}\n{snippet}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug("[KB] %s", e)
    return ""


def _inj_mkb_str(ctx):
    """K-08：methodology_knowledge_base 知识金矿注入器。

    从 2524 条结构化知识条目中按资产名+报告类型选择最相关的 6 条，
    格式化为方法论参考块注入写作 prompt。
    """
    try:
        from core.methodology_kb import build_block

        keywords = [ctx.get("asset", ""), ctx.get("report_type", "")]
        # 从行业标签补充关键词
        biz = (ctx.get("data_context") or {}).get("biz_model")
        if isinstance(biz, dict):
            tags = biz.get("industry_tags") or []
            keywords.extend(str(t) for t in tags[:3])
        keywords = [k for k in keywords if k and len(k) >= 2]
        if not keywords:
            return ""
        return build_block(keywords, report_type=ctx.get("report_type", ""))
    except Exception as e:
        logger.debug("[MKB] %s", e)
    return ""


def _inj_macro_str(ctx):
    """K-10：宏观背景注入器——global_macro.json → Fed/CPI/GDP 快照。"""
    try:
        from core.macro_context import block

        return block()
    except Exception as e:
        logger.debug("[MACRO] %s", e)
    return ""
