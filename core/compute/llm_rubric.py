"""llm_rubric.py — LLM 维度评分（2026-08-08 系统级优化）

顶级打法（G-Eval）：用 LLM 按 rubric 打分，结合自洽性。规则门禁抓硬伤，LLM 评分抓软质量。

本模块：对报告按维度 rubric 让 LLM 打分（数据密度/论证深度/去AI化/决策质量），
供 IronGate 双轨（规则 + LLM 软质量）。

用法：
  from core.compute.llm_rubric import llm_score_report
  result = llm_score_report(report_text)  # 返回各维度评分
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("2hao.llm_rubric")

# G-Eval 风格 rubric（各维度评分标准）
RUBRIC = {
    "data_density": {
        "desc": "数据密度：每个判断是否有数据支撑，来源是否标注",
        "anchor": {"5": "数据丰富且全部带来源", "3": "有数据但部分无来源", "1": "无数据纯定性"},
    },
    "argument_depth": {
        "desc": "论证深度：因果链是否完整，反方论证是否充分",
        "anchor": {"5": "多层因果+强反方", "3": "单层因果+有反方", "1": "无因果无反方"},
    },
    "aigc_fingerprint": {
        "desc": "去AI化：是否像人类分析师，无元评论/工作过程语言",
        "anchor": {"5": "纯专业口吻", "3": "少量AI痕迹", "1": "明显AI痕迹"},
    },
    "decision_quality": {
        "desc": "决策质量：结论是否清晰，依据是否充分，是否可执行",
        "anchor": {"5": "结论清晰可执行", "3": "结论有但模糊", "1": "无结论"},
    },
}


def _rubric_prompt(text: str) -> str:
    parts = ["请按以下 rubric 对报告打分（每维 1-5，附一句理由）："]
    for dim, spec in RUBRIC.items():
        parts.append(f"\n[{dim}] {spec['desc']}")
        parts.append(f"  5分: {spec['anchor']['5']}")
        parts.append(f"  3分: {spec['anchor']['3']}")
        parts.append(f"  1分: {spec['anchor']['1']}")
    parts.append("\n报告文本（截断）:")
    parts.append(text[:4000])
    parts.append('\n输出JSON: {"data_density": 4, "argument_depth": 3, ...}')
    return "\n".join(parts)


def llm_score_report(report_text: str, use_llm: bool = True) -> dict:
    """LLM 维度评分。

    use_llm=True 调 LLM；False 返回规则近似（占位）。
    """
    if not report_text or len(report_text) < 10:
        return {"status": "no_text"}

    if not use_llm:
        # 规则近似：简单启发式
        return _rule_based_score(report_text)

    try:
        from core.deepseek_client import call_llm

        r = call_llm([{"role": "user", "content": _rubric_prompt(report_text)}], temperature=0.1, max_tokens=500)
        content = r["choices"][0]["message"]["content"]
        import re

        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            scores = json.loads(m.group())
            return {
                "status": "ok",
                "scores": scores,
                "overall": round(sum(v for v in scores.values() if isinstance(v, (int, float))) / len(scores), 2),
            }
    except Exception as e:
        logger.debug("[LLM-RUBRIC] %s", str(e)[:60])
    return _rule_based_score(report_text)


def _rule_based_score(report_text: str) -> dict:
    """规则近似评分（无 LLM 时兜底）。"""
    text = report_text
    # 数据密度：来源标注数
    source_cnt = text.count("（") + text.count("来源") + text.count("据")
    data_density = min(5, 1 + source_cnt // 5)
    # 论证深度：反方/因果词
    arg_cnt = sum(text.count(k) for k in ["因此", "然而", "但", "反方", "因为"])
    argument_depth = min(5, 1 + arg_cnt // 5)
    # 去AI化：AI痕迹词
    from core.template_blacklist import scan_metacomment, scan_work_process

    mc = scan_metacomment(text)
    wp = scan_work_process(text)
    ai_marks = mc["total"] + wp["total"]
    aigc_fingerprint = max(1, 5 - ai_marks * 2)
    # 决策质量：结论词
    dec_cnt = sum(text.count(k) for k in ["结论", "建议", "评级", "进入", "退出"])
    decision_quality = min(5, 1 + dec_cnt // 3)
    scores = {
        "data_density": data_density,
        "argument_depth": argument_depth,
        "aigc_fingerprint": aigc_fingerprint,
        "decision_quality": decision_quality,
    }
    return {"status": "rule_based", "scores": scores, "overall": round(sum(scores.values()) / len(scores), 2)}


def build_prompt(result: dict) -> str:
    """生成注入门禁的评分说明。"""
    if result.get("status") not in ("ok", "rule_based"):
        return ""
    s = result["scores"]
    return (
        f"LLM 维度评分（{result['status']}）：数据密度{s.get('data_density')}/5 "
        f"论证深度{s.get('argument_depth')}/5 去AI化{s.get('aigc_fingerprint')}/5 "
        f"决策质量{s.get('decision_quality')}/5 → 综合 {result['overall']}/5"
    )
