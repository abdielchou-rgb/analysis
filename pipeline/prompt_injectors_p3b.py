# -*- coding: utf-8 -*-
"""P3-B 追加注入器（方法论置信度 / [E#] 证据清单 / 研究问题树）。

与 prompt_injectors.py 同契约：纯函数 `(ctx) -> str`。
在此独立成文件以便增量演进；注册仍集中在 prompt_injectors.INJECTORS。
"""

from __future__ import annotations

import logging
from pathlib import Path

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


# ── K-09~K-15 批量资产激活注入器 ──────────────────────────────


def _inj_valuation_kb_str(ctx):
    """投行估值模型全知识库（131KB）→ 估值方法论参考。"""
    try:
        import json

        fp = Path(__file__).resolve().parent.parent / "data" / "投行估值模型全知识库.json"
        d = json.loads(fp.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            lines = ["## [投行估值模型知识库]"]
            for k, v in list(d.items())[:6]:
                summary = str(v)[:200]
                lines.append("  [" + k + "] " + summary)
            return "\n".join(lines)
    except Exception as e:
        logger.debug("[VAL-KB] %s", e)
    return ""


def _inj_policy_str(ctx):
    """K-12：政策文库注入器。"""
    try:
        import json

        dc = ctx.get("data_context") or {}
        biz = dc.get("biz_model") or {}
        tags = [str(t) for t in (biz.get("industry_tags") or [])] if isinstance(biz, dict) else []
        fp = Path(__file__).resolve().parent.parent / "data" / "policy_library.json"
        d = json.loads(fp.read_text(encoding="utf-8"))
        policies = d.get("policies", []) if isinstance(d, dict) else []
        if not policies:
            return ""
        relevant = [
            p
            for p in policies[:100]
            if any(str(t).lower() in str(p.get("title", "")).lower() for t in tags if len(t) >= 2)
        ]
        if not relevant:
            relevant = policies[-3:]
        lines = ["## [政策文库参考] 近期相关政策："]
        for p in relevant[:5]:
            lines.append("  [" + str(p.get("date", "")) + "] " + str(p.get("title", ""))[:100])
        return "\n".join(lines)
    except Exception as e:
        logger.debug("[POLICY] %s", e)
    return ""


def _inj_esg_data_str(ctx):
    """行业 ESG 数据注入器。"""
    try:
        import json

        dc = ctx.get("data_context") or {}
        biz = dc.get("biz_model") or {}
        tags = [str(t) for t in (biz.get("industry_tags") or [])] if isinstance(biz, dict) else []
        fp = Path(__file__).resolve().parent.parent / "data" / "industry_esg.json"
        d = json.loads(fp.read_text(encoding="utf-8"))
        matched = None
        for ind_key, esg_data in d.items():
            if any(t.lower() in ind_key.lower() for t in tags if len(t) >= 2):
                matched = esg_data
                break
        if not matched:
            return ""
        lines = ["## [行业ESG数据]"]
        if isinstance(matched, dict):
            for k, v in list(matched.items())[:5]:
                lines.append("  " + k + ": " + str(v)[:100])
        return "\n".join(lines)
    except Exception as e:
        logger.debug("[ESG-DATA] %s", e)
    return ""


def _inj_ma_cases_str(ctx):
    """M&A 可比案例注入器。"""
    try:
        import json

        base = Path(__file__).resolve().parent.parent / "data"
        cases_fp = base / "m_and_a_cases.json"
        ev_fp = base / "m_and_a_ev_ebitda.json"
        cases = json.loads(cases_fp.read_text(encoding="utf-8")) if cases_fp.exists() else []
        ev = json.loads(ev_fp.read_text(encoding="utf-8")) if ev_fp.exists() else {}
        dc = ctx.get("data_context") or {}
        biz = dc.get("biz_model") or {}
        tags = [str(t) for t in (biz.get("industry_tags") or [])] if isinstance(biz, dict) else []
        relevant = [
            c
            for c in (cases if isinstance(cases, list) else [])
            if any(str(t).lower() in str(c.get("industry", "")).lower() for t in tags if len(t) >= 2)
        ]
        if not relevant:
            relevant = (cases if isinstance(cases, list) else [])[-3:]
        lines = ["## [M&A可比案例]"]
        for c in relevant[:4]:
            if isinstance(c, dict):
                lines.append(
                    "  "
                    + c.get("acquirer", "?")
                    + " → "
                    + c.get("target", "?")
                    + ": EV/EBITDA "
                    + str(c.get("ev_ebitda", "N/A"))
                )
        if isinstance(ev, dict) and ev:
            lines.append("  行业EV/EBITDA中位数: " + str(ev.get("median", "N/A")))
        return "\n".join(lines)
    except Exception as e:
        logger.debug("[MA-CASES] %s", e)
    return ""


def _inj_segment_rev_str(ctx):
    """segment_revenue 注入器——分部收入拆分。"""
    try:
        import json

        code = ctx.get("asset_code", "")
        if not code:
            return ""
        fp = Path(__file__).resolve().parent.parent / "data" / "segment_revenue.json"
        d = json.loads(fp.read_text(encoding="utf-8"))
        entry = d.get(code, {}) if isinstance(d, dict) else {}
        if not entry:
            return ""
        lines = ["## [分部收入拆分]"]
        if isinstance(entry, dict):
            for seg, val in list(entry.items())[:8]:
                lines.append("  " + seg + ": " + str(val))
        return "\n".join(lines)
    except Exception as e:
        logger.debug("[SEGMENT] %s", e)
    return ""


def _inj_consulting_str(ctx):
    """methodology_consulting_deep 注入器——MBB 方法论补充。"""
    try:
        import json

        fp = Path(__file__).resolve().parent.parent / "data" / "methodology_consulting_deep.json"
        d = json.loads(fp.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            lines = ["## [MBB咨询方法论补充]"]
            for k, v in list(d.items())[:5]:
                lines.append("  [" + k + "] " + str(v)[:150])
            return "\n".join(lines)
        elif isinstance(d, list):
            lines = ["## [MBB咨询方法论补充]"]
            for item in d[:5]:
                if isinstance(item, dict):
                    lines.append("  [" + item.get("name", "") + "] " + str(item.get("implication", ""))[:150])
            return "\n".join(lines)
    except Exception as e:
        logger.debug("[CONSULTING] %s", e)
    return ""


def _inj_market_seg_str(ctx):
    """global_market_segments 注入器。"""
    try:
        import json

        fp = Path(__file__).resolve().parent.parent / "data" / "global_market_segments.json"
        d = json.loads(fp.read_text(encoding="utf-8"))
        if isinstance(d, dict) and d:
            lines = ["## [全球市场细分参考]"]
            for k, v in list(d.items())[:6]:
                lines.append("  " + k + ": " + str(v)[:100])
            return "\n".join(lines)
    except Exception as e:
        logger.debug("[MKT-SEG] %s", e)
    return ""


def _inj_analogy_str(ctx):
    """P3-B：跨行业类比注入器——按行业特征签名匹配历史案例。"""
    try:
        from core.cross_industry import build_block

        dc = ctx.get("data_context") or {}
        biz = dc.get("biz_model") or {}
        industry = ""
        if isinstance(biz, dict):
            tags = biz.get("industry_tags") or []
            if tags:
                industry = str(tags[0])
        if not industry:
            industry = ctx.get("asset", "")
        growth = dc.get("industry_growth")
        cr3 = dc.get("cr3")
        return build_block(
            industry,
            growth_rate=growth,
            cr3=cr3,
            capital_intensity="重资产",
            tech_cycle="中等迭代",
        )
    except Exception as e:
        logger.debug("[ANALOGY] %s", e)
    return ""
