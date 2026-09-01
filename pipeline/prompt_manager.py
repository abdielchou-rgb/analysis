"""
pipeline/prompt_manager.py — Prompt 管理器

从 section_writer.py 提取并增强：
1. 系统前缀管理（Prompt Caching 优化）
2. 机构人格卡注入
3. 写作 DNA 注入
4. 方法论框架注入
5. 报告蓝图注入
6. 状态锚点注入（收敛机制）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("2hao.prompt_manager")

_ROOT = Path(__file__).resolve().parent.parent

# ── P1-3 Prompt Caching 前缀（2026-08-07）────────────────────
# DeepSeek 自动磁盘缓存：前缀稳定的 system prompt 跨调用命中缓存，成本近零。
# 写宪章/口径/禁语等"所有节点共享的静态约束"放这里，变量（数据/大纲/反馈）放 user。
# 变更此常量时手动加版本注释（缓存 key 变化，命中率重置）。
_LLM_SYSTEM_PREFIX = (
    "## [格式] 用规范的Markdown层级标题(一、二、三编号章节 + #主标题/##章节/###小节)。无问候语。\n"
    "## [数据标注] 每个数值必须紧跟类型标注：\n"
    "  (A)=Actual实际值(公司披露/年报/公告)\n"
    "  (E)=Estimate估算值(基于模型/假设推算)\n"
    "  (F)=Forecast预测值(前瞻判断/指引)\n"
    "  (B)=Benchmark基准值(同业/行业对标)\n"
    "  示例: 2025年营收6.88亿(A)，2026年预计8.5亿(F)，可比公司平均PS 8x(B)。至少3个表格。\n"
    "## [来源] 每个数值标注具体来源(报告名称+机构+日期)。\n"
    "## [禁止] 禁止主观评分(X/10分)。禁止第一人称。禁止编造数据。\n"
    "## [数据缺口] 若某维度数据无法获取，必须明确写'数据有限/待尽调核实，暂无法获取，"
    "已记录信息缺口'，禁止编造。诚实标注缺口优于伪造数据。\n"
    "## [结构] 每段必须有So What链。每个判断必须有反方论证（三段式：情境→机制→杀伤力，禁止'概率XX%'空壳）。\n"
    "## [篇幅] 本部分不得少于3500字，必须展开每个维度的全部二级子问题，禁止精简缩略。\n直接写正文。\n"
    "## [结构化思考-ISCoT] 写正文前必须先内部分三步思考（不输出思考过程）：\n"
    "  1) 本段要论证的核心判断（claim）是什么？\n"
    "  2) 支撑证据是什么（用上面数据，禁止编造）？推理链如何展开？\n"
    "  3) 与前后文如何衔接？本段在报告树中的位置是什么？\n"
    "  想清楚再写，禁止跳跃、跑题、重复上一段观点（长文崩溃防护，ACL 2026 IS-CoT）。\n"
    "## [自检-反思·专业怀疑] 写完后以审计师怀疑姿态自查（不输出过程）：\n"
    "  1) 每个数字是否有标注（A/E/F/B）和来源？无来源数字=硬伤。\n"
    "  2) 反方论证（三段式）？\n"
    "  3) 是否与上文的数字/口径冲突？冲突必须修正，禁止带病出门。\n"
    "  4) [专业怀疑] 假设你写的数据可能有错：哪个数字最可能被验证为错？\n"
    "     最可能错的是：心算的比例/比率、记忆的行业数据、跨章节的同一指标。\n"
    "     对这些点，能引代码算好的值就引，没有就标(E)或'待尽调'，禁止自信写错。\n"
    "  自查发现硬伤 → 就地修正后再输出最终正文（四大专业怀疑 + R2-Write）。\n"
)


@dataclass
class PromptContext:
    """Prompt 上下文"""

    report_type: str = "industry_deep"
    style: str = "cicc"
    asset: str = ""
    seg_idx: int = 0
    skeleton_mode: bool = False
    data_context: Optional[dict] = None
    gate_feedback: str = ""
    learning_findings: str = ""
    state_anchor: Optional[dict] = None
    prev_summary: str = ""


class PromptManager:
    """
    Prompt 管理器

    职责：
    1. 构建系统前缀（含 Prompt Caching 优化）
    2. 注入机构人格卡
    3. 注入写作 DNA
    4. 注入方法论框架
    5. 注入报告蓝图
    6. 注入状态锚点（收敛机制）
    7. 注入 Gate 反馈
    """

    def __init__(self, report_type: str = "industry_deep", style: str = "cicc"):
        self.report_type = report_type
        self.style = style

    def build_system_prompt(self, ctx: PromptContext) -> str:
        """
        构建系统提示词

        Args:
            ctx: Prompt 上下文

        Returns:
            str: 系统提示词
        """
        sp = _LLM_SYSTEM_PREFIX

        # 决策备忘录特殊约束
        if ctx.report_type == "decision_memo":
            sp += self._build_decision_memo_constraints()

        # 机构人格卡
        persona = self._load_persona(ctx.style)
        if persona:
            sp += f"\n## [机构人格]\n{persona[:1800]}"

        # 写作 DNA
        dna = self._load_writing_dna(ctx.style)
        if dna:
            sp += f"\n{dna}"

        return sp

    def build_user_prompt(
        self,
        ctx: PromptContext,
        scaffold_section: str = "",
        data_str: str = "",
        chart_md: str = "",
        calib_str: str = "",
        plan_str: str = "",
        method_ref: str = "",
        institution_baseline: str = "",
        framework_injection: str = "",
        research_protocol: str = "",
        report_blueprint: str = "",
    ) -> str:
        """
        构建用户提示词

        Args:
            ctx: Prompt 上下文
            scaffold_section: 章节骨架
            data_str: 数据字符串
            chart_md: 图表 Markdown
            calib_str: 校准字符串
            plan_str: 计划字符串
            method_ref: 方法论参考
            institution_baseline: 机构基准
            framework_injection: 框架注入
            research_protocol: 研究协议
            report_blueprint: 报告蓝图

        Returns:
            str: 用户提示词
        """
        parts = []

        # 数据注入
        if data_str:
            parts.append("## [可用数据]")
            parts.append(data_str)
            parts.append("")

        # 图表注入
        if chart_md:
            parts.append("## [图表数据]")
            parts.append(chart_md)
            parts.append("")

        # 校准注入
        if calib_str:
            parts.append(calib_str)
            parts.append("")

        # 计划注入
        if plan_str:
            parts.append(plan_str)
            parts.append("")

        # 方法论参考
        if method_ref:
            parts.append(method_ref)
            parts.append("")

        # 机构基准
        if institution_baseline:
            parts.append(institution_baseline)
            parts.append("")

        # 框架注入
        if framework_injection:
            parts.append(framework_injection)
            parts.append("")

        # 研究协议
        if research_protocol:
            parts.append(research_protocol)
            parts.append("")

        # 报告蓝图
        if report_blueprint:
            parts.append(report_blueprint)
            parts.append("")

        # 章节骨架（唯一结构）
        if scaffold_section:
            parts.append("")
            parts.append("## [章节骨架-唯一] 以下为本段唯一的结构骨架，必须严格按其组织：")
            parts.append(scaffold_section)
            parts.append("[/骨架] 报告蓝图/方法论片段仅作思路参考，禁止产生第二套章节编号。")

        # 前段摘要
        if ctx.prev_summary:
            parts.append("")
            parts.append("## 前段摘要")
            parts.append(ctx.prev_summary)

        # Gate 反馈
        if ctx.gate_feedback:
            parts.append("")
            parts.append("## 上一轮评审反馈")
            parts.append(ctx.gate_feedback)

        # 历史学习反馈
        if ctx.learning_findings:
            parts.append("")
            parts.append("## 历史学习反馈")
            parts.append(ctx.learning_findings)

        # 状态锚点（收敛机制）
        if ctx.state_anchor and isinstance(ctx.state_anchor, dict):
            parts.append("")
            parts.append("## [上一轮状态锚点（必须参考，勿重复已覆盖内容）]")
            prev_text = ctx.state_anchor.get("prev_full_text", "")
            prev_cov = ctx.state_anchor.get("prev_coverage", {})
            targets = ctx.state_anchor.get("revision_targets", [])
            if prev_cov:
                cov_detail = prev_cov.get("details", "")
                parts.append(f"- 上一轮 SAC 维度覆盖: {cov_detail}")
            if targets:
                parts.append("- 本轮必须修复的项（修订目标）:")
                for t in targets:
                    parts.append(f"  - {t}")
            if prev_text:
                parts.append(f"- 上一轮全文开头节选（前{len(prev_text[:1200])}字）:")
                parts.append(prev_text[:1200])
            parts.append(
                "- 注意：已覆盖维度不要从零重写，只针对缺失/失败项修订；保持已达标部分（数据口径、章节结构）不变。"
            )
            # 跨轮退化信号
            if ctx.state_anchor.get("regression"):
                parts.append(
                    "- [⚠️ 跨轮退化] 上一轮质量比前一轮下降。禁止整体推倒重写，"
                    "必须基于上一轮全文做针对性修订，只改导致退化的部分。"
                )

        return "\n".join(parts)

    def _build_decision_memo_constraints(self) -> str:
        """构建决策备忘录特殊约束"""
        constraints = (
            "\n## [决策锚定-强约束] 全文所有数字与竞品名以【可用数据】与"
            "【共享数据字典】为唯一来源；任何不在数据中的市场规模/竞品/价格锚一律禁止。"
            "关键结论需可复算（保留分子分母）。\n"
        )
        constraints += (
            "\n## [叙事越界禁令] 仅可使用【可用数据】中出现的实体与行业叙事；"
            "若发现自身试图引入数据中不存在的公司/技术路线/政策链，立即停止——"
            "如需补充行业常识，标注(E)估算+来源，不得冒充 enrich 数据。\n"
        )
        constraints += (
            "\n## [执行摘要强制] 执行摘要必须一句话给出：结论(进/不进/条件性进)"
            "+卡位评分(如有数据)+投入量级+最坏损失上限+执行前提。"
            "涉及主体必须使用数据中的真实公司名，禁止匿名化或代入其他标的名。"
        )
        return constraints

    def _load_persona(self, style: str) -> str:
        """加载机构人格卡"""
        try:
            persona_map = {
                "cicc": "cicc_analyst.md",
                "gs": "goldman_sachs.md",
                "mck": "mckinsey_consultant.md",
            }
            pf = _ROOT / "prompts" / "system" / persona_map.get(style, "common_principles.md")
            if pf.exists():
                return pf.read_text(encoding="utf-8")[:1800]
        except Exception:
            pass
        return ""

    def _load_writing_dna(self, style: str) -> str:
        """加载写作 DNA"""
        try:
            from utils.writing_dna import get_dna

            dna = get_dna(style or "")
            if dna and getattr(dna, "institution_name", ""):
                _ps = dna.paragraph_start or {}
                _un = dna.uncertainty or {}
                _fp = dna.first_person or {}
                return (
                    f"## [机构写作DNA·{dna.institution_name}] "
                    f"判断动词首选『{dna.judgment_verbs.get('primary', '')}』；"
                    f"段首避免 {'/'.join(_ps.get('avoid', [])[:3]) or '无'}；"
                    f"不确定表述用 {'/'.join(_un.get('preferred', []))}，"
                    f"禁用 {'/'.join(_un.get('avoid', []))}；"
                    f"'我们'频率≈{_fp.get('we_frequency', 0.8):.0%}。"
                )
        except Exception:
            pass
        return ""

    def build_methodology_reference(self, seg_idx: int) -> str:
        """
        构建方法论参考

        按 segment 注入相关方法论（宏观/策略/生命周期等真实框架）
        """
        try:
            import json as _json

            # 三级优先（宏观方法论）
            _paths = [
                _ROOT / "data" / "methodology_macro_deep.json",
                _ROOT / "data" / "methodology_macro_absorbed.json",
                _ROOT / "data" / "methodology_frameworks_detailed.json",
            ]
            detailed = None
            for _p in _paths:
                if _p.exists():
                    try:
                        detailed = _json.loads(_p.read_text(encoding="utf-8"))
                        if detailed:
                            break
                    except Exception:
                        continue
            if not detailed:
                return ""

            # 加载深度吸收产物
            _kb = {}
            for _name in (
                "methodology_industry_deep",
                "methodology_valuation_deep",
                "methodology_reports_deep",
                "methodology_backtest_deep",
                "methodology_consulting_deep",
                "methodology_audit_deep",
            ):
                _p = _ROOT / "data" / f"{_name}.json"
                if _p.exists():
                    try:
                        _kb[_name] = _json.loads(_p.read_text(encoding="utf-8"))
                    except Exception:
                        continue

            # segment 0(战略层) → 生命周期/商业模式/行业框架
            # segment 1(竞争层) → 策略/行业竞争/研报范式
            # segment 2(前瞻层) → 估值/宏观/回测基准
            topic_map = {
                0: ["business_model", "industry_lifecycle"],
                1: ["strategy"],
                2: ["valuation", "macro"],
            }
            topics = topic_map.get(seg_idx, [])

            parts = ["## 方法论参考"]
            for topic in topics:
                if topic in detailed:
                    parts.append(f"### {topic}")
                    parts.append(str(detailed[topic])[:500])

            # 添加深度吸收产物
            for name, kb in _kb.items():
                if kb:
                    parts.append(f"### {name}")
                    parts.append(str(kb)[:300])

            return "\n".join(parts) if len(parts) > 1 else ""
        except Exception:
            return ""

    def build_institution_baseline(self) -> str:
        """
        构建机构写作基准

        从 absorbed_baseline.json 读取真实顶级机构研报的写作密度目标
        """
        try:
            import json as _json

            _path = _ROOT / "data" / "absorbed_baseline.json"
            if not _path.exists():
                return ""
            base = _json.loads(_path.read_text(encoding="utf-8"))
            targets = []
            for cat in ("券商报告", "深度报告", "all"):
                agg = base.get(cat) if isinstance(base, dict) else None
                if isinstance(agg, dict) and agg.get("count", 0) > 0:
                    targets.append(
                        f"{cat}: 判断密度={agg.get('avg_judgment_density', 0):.1f}/千字 "
                        f"反共识={agg.get('avg_counter_density', 0):.2f}/千字 "
                        f"经验引用={agg.get('avg_experience_refs', 0):.1f} "
                        f"不确定性={agg.get('avg_uncertainty', 0):.1f}"
                    )
            if not targets:
                return ""
            lines = [
                "## 机构写作基准（对标顶级机构研报统计）",
                "以下为真实顶级机构研报的写作密度统计，你的正文应达到相近密度（判断密度尤其重要）：",
            ]
            lines.extend(f"- {t}" for t in targets)
            lines.append("重点：保持高判断密度（多用'我们认为/预计/判断'），体现反共识观点，标注数据来源。")
            lines.append("")
            return "\n".join(lines)
        except Exception:
            return ""

    def build_report_blueprint(self, seg_idx: int) -> str:
        """
        构建报告蓝图

        注入结构化章节模板
        """
        try:
            from core.report_blueprint import ReportBlueprint

            bp = ReportBlueprint(self.report_type, self.style)
            sections = bp.get_sections_for_segment(seg_idx) if hasattr(bp, "get_sections_for_segment") else []
            if sections:
                parts = ["[报告蓝图 - 本段建议结构]"]
                for s in sections[:5]:
                    title = s.get("title", "?") if isinstance(s, dict) else str(s)
                    parts.append(f"  - {title}")
                parts.append("[/蓝图]")
                return "\n".join(parts)
            return ""
        except Exception:
            return ""

    def build_research_protocol(self) -> str:
        """
        构建研究协议

        MECE + Serenity 9-step research protocol injection
        """
        try:
            from core.protocol import SACToResearchProtocol

            rp = SACToResearchProtocol()
            # 需要 SAC 实例，这里简化处理
            protocol = rp.generate(None, output_depth="standard")
            if protocol and hasattr(protocol, "to_agent_brief"):
                brief = protocol.to_agent_brief()
                if brief and len(brief) > 50:
                    return "\n=== MECE + Serenity 研究协议 ===\n" + brief[:600] + "\n=== 协议结束 ===\n"
            return ""
        except Exception as e:
            logger.debug("[PROTOCOL] %s", e)
            return ""
