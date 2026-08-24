"""V51 T2b Prose Engine — section-by-section generation from ArgumentScaffold.

Design:
  - T2a generates ArgumentScaffold (zero-LLM, deterministic)
  - T2b produces prose (LLM-assisted by default, template fallback)
  - Sections are independent; one failure doesn't block others
  - DeepSeek v4-pro support for Chinese financial report generation
"""

from __future__ import annotations

import json, logging, os, re
from typing import Optional

from core.models import ArgumentScaffold, ArgumentSection, KnowledgePackage, WritingBrief

logger = logging.getLogger("v51.t2b.prose")

_HAS_OPENAI = False
try: from openai import OpenAI; _HAS_OPENAI = True
except ImportError: pass

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
HAS_LLM = bool(DEEPSEEK_KEY)


SECTION_TEMPLATES = {
    "core_disagreement": "## 核心分歧\n\n市场一致预期认为「{market_consensus}」。{our_view_statement}\n\n分歧的核心变量在于「{key_variable}」。\n\n反方观点同样值得正视：{counter_view}。\n\n",
    "business_model": "## 商业模式\n\n{thesis}\n\n{evidence_text}\n\n{data_gap_text}",
    "financial_analysis": "## 财务分析\n\n结论先行：{thesis}\n\n{evidence_text}\n\n需指出反方证据：{counter_text}\n",
    "competitive_position": "## 竞争格局\n\n{thesis}\n\n{evidence_text}\n\n反方必须正视：{counter_text}",
    "growth_drivers": "## 增长驱动\n\n{thesis}\n\n{evidence_text}\n\n关键跟踪变量：{key_variable_text}",
    "governance_esg": "## 治理与ESG\n\n{thesis}\n\n{evidence_text}\n\n风险点：{counter_text}",
    "valuation_assessment": "## 估值分析\n\n{thesis}\n\n{evidence_text}\n\n反方情景必须正视：{counter_text}",
    "falsification": "## 证伪条件\n\n以下可观察变化中任何一条出现，将推翻本报告核心判断：\n\n{falsify_items}\n",
    "profit": "## 产业链与利润池\n\n{thesis}\n\n{evidence_text}\n{data_gap_text}",
    "compete": "## 竞争格局\n\n{thesis}\n\n{evidence_text}\n{data_gap_text}",
    "market": "## 市场空间\n\n{thesis}\n\n{evidence_text}\n{data_gap_text}",
    "tech": "## 技术路线\n\n{thesis}\n\n{evidence_text}\n{data_gap_text}",
    "policy": "## 政策传导\n\n{thesis}\n\n{evidence_text}\n{data_gap_text}",
    "capital": "## 资本市场映射\n\n{thesis}\n\n{evidence_text}\n{data_gap_text}",
    "default": "## {section_title}\n\n{thesis}\n\n{evidence_text}\n{data_gap_text}",
}


def _fmt_ev(section, kp):
    pool = {dp.name: dp for dp in (kp.data_points or [])}
    parts = []
    for eid in section.evidence_ids[:5]:
        dp = pool.get(eid)
        if dp and dp.value is not None:
            src = f"（来源：{dp.source}）" if dp.source else ""
            parts.append(f"{dp.name}约{dp.value}{dp.unit or ''}{src}")
    if parts:
        return "关键数据：" + "；".join(parts[:3]) + "。" + ("此外，" + "；".join(parts[3:5]) + "。" if len(parts) > 3 else "")
    return "相关数据需进一步调研。"


def _render_template(section, kp, brief):
    tid = section.section_id if section.section_id in SECTION_TEMPLATES else "default"
    tpl = SECTION_TEMPLATES[tid]
    et = _fmt_ev(section, kp)
    gt = "数据缺口：" + "；".join(section.data_gaps[:3]) + "（待补充）" if section.data_gaps else ""
    ct = section.counter_thesis or "反方观点需进一步论证。"
    kv = brief.key_variable or "需补充关键变量"
    fi = "\n".join(f"{i+1}. {item}" for i, item in enumerate(section.sub_points or [
        "核心指标连续两个报告期不及预期", "与判断方向相反的结构性变化出现",
        "关键假设被宏观或行业变化证伪"], 3))
    ctx = {"section_title": section.title, "thesis": section.thesis or "",
           "evidence_text": et or "相关数据待补充。", "data_gap_text": gt,
           "counter_text": ct, "market_consensus": brief.market_consensus or "市场一致预期",
           "our_view_statement": f"我们判断{brief.our_view or section.thesis}" if (brief.our_view or section.thesis) else "需补充核心判断。",
           "key_variable": kv, "key_variable_text": f"重点关注《{kv}》的变化趋势。",
           "counter_view": ct, "falsify_items": fi}
    try: return tpl.format(**ctx)
    except KeyError: return f"## {section.title}\n\n{section.thesis}\n\n{et}"


def _build_prompt(section, kp, brief, style_profile) -> str:
    ev = []
    sources_used = set()
    for eid in section.evidence_ids[:8]:
        dp = next((d for d in (kp.data_points or []) if d.name == eid), None)
        if dp and dp.value is not None:
            ev.append(f"- {dp.name}: {dp.value} {dp.unit or ''}（来源：{dp.source or '系统计算'}）")
            if dp.source:
                sources_used.add(dp.source)
    ev_str = "\n".join(ev) or "（暂无可用数据）"
    ft_list = (style_profile or {}).get("writing", {}).get("forbidden_terms", [])
    ft_str = f"禁用措辞：{'、'.join(ft_list)}。" if ft_list else ""
    cs = section.counter_thesis or "需补充反方观点"

    # 可用来源白名单 —— Karpathy: 提前阻止而非事后验证
    valid_sources = {"eastmoney", "年报", "公告", "公司年报", "交易所", "证监会",
                     "赛迪顾问", "Yole", "ICV Tank", "行业测算", "wind", "bloomberg",
                     "公司官网", "招股书", "定期报告", "行业公开报道", "系统计算", "tencent_kline"}
    all_valid = "、".join(sorted(valid_sources))
    used_str = "、".join(sorted(sources_used)) if sources_used else all_valid

    return f"""撰写专业投资研究报告的一节。

标题：{section.title}
核心判断：{section.thesis}
反方观点：{cs}
可用证据：
{ev_str}

重要约束 —— 来源准确：
- 你只能引用以下来源之一：{used_str}
- 不得编造来源，不得使用"据研究" "据调查" "据统计" 等模糊引用
- 如果数据不足，标注"待补充"，不编造数字
- 每个数字必须带来源标注

写作要求：
- 结论先行：每段以判断句开头
- 每个判断必须有反方或条件限制
- 使用"我们"而非"我"
- 不使用模糊词（显著、大量、明显）
{ft_str}
直接输出此节正文，不含元信息。"""


def _call_deepseek(prompt: str) -> Optional[str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500, temperature=0.5,
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.warning(f"DeepSeek call failed: {e}")
        return None


class ProseEngine:
    """Section-by-section prose generator."""

    def __init__(self, mode: str = ""):
        if not mode:
            mode = "llm" if HAS_LLM else "hybrid"
        self.mode = mode
        if mode == "llm" and not HAS_LLM:
            logger.warning("no key, fallback to hybrid")
            self.mode = "hybrid"