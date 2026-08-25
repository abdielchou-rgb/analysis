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
