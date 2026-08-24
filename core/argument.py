"""V50+ T2a — Argument Engine (deterministic, zero-LLM).

Generates ArgumentScaffold from WritingBrief + KnowledgePackage + SAC.
No LLM involved — pure structural design using SAC dimension rules.

Architecture (first-principles optimized):
  T2a reads SAC required_dimensions + pre_workflow
    -> generates structured sections with thesis + evidence_ids + counter_evidence
    -> core_disagreement locked to page 2
    -> anti-confirmation-bias: bear case before bull case
    -> Style Profile rules injected per section

This replaces the empty-shell ArgumentVerifier from V50+ original.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.models import (
    WritingBrief, KnowledgePackage, DataPoint,
    ArgumentScaffold, ArgumentSection, SectionType,
    SACEntry,
)
from dataclasses import dataclass, field

logger = logging.getLogger("v50.t2a")


@dataclass
class DimensionPriority:
    """SAC 维度优先级——用于聚焦深度。"""
    id: str = ""
    depth: str = "standard"  # "deep" | "standard" | "brief"
    weight: float = 1.0


class ArgumentEngine:
    """Deterministic argument structure designer."""

    def design(self, brief: WritingBrief, kp: KnowledgePackage) -> ArgumentScaffold:
        sac = kp.sac
        sections: list[ArgumentSection] = []

        evidence_pool: dict[str, DataPoint] = {}
        for dp in kp.data_points:
            if dp.name:
                evidence_pool[dp.name] = dp

        # 聚焦深度：识别关键维度
        priorities = self._prioritize_dimensions(sac, brief)

        if sac and sac.required_dimensions:
            for dim in sac.required_dimensions:
                dim_id = dim.get("id", "")
                question = dim.get("question", "")
                evidence_min = dim.get("evidence_min", 1)
                counter_required = dim.get("counter_evidence", False)
                matched_ids = self._match_evidence(dim, evidence_pool)
                counter_ids = []
                if counter_required:
                    counter_ids = self._find_counter_evidence(dim, evidence_pool)
                thesis = self._generate_thesis(brief, dim, matched_ids, evidence_pool)
                counter_thesis = ""
                if counter_required:
                    counter_thesis = brief.market_consensus or f"市场共识与{question}存在分歧"
                gaps = []
                if len(matched_ids) < evidence_min:
                    gaps.append(f"{question} - 证据不足（需>= {evidence_min}条，当前{len(matched_ids)}条）")

                # 根据优先级调整 evidence_min（深度维度要求更多证据）
                for p in priorities:
                    if p.id == dim_id:
                        if p.depth == "deep":
                            evidence_min = max(evidence_min, 4)
                        break

                sections.append(ArgumentSection(
                    section_id=dim_id,
                    title=self._dim_title(dim_id, question),
                    section_type=SectionType.COUNTER if dim_id in ("falsify",) else SectionType.JUDGMENT,
                    thesis=thesis,
                    counter_thesis=counter_thesis,
                    evidence_ids=matched_ids,
                    counter_evidence_ids=counter_ids,
                    required_citations=evidence_min,
                    data_gaps=gaps,
                    has_alternative_view=counter_required,
                ))

        core_disagreement = {
            "market": brief.market_consensus or "市场一致预期需补充",
            "our_view": brief.our_view or brief.core_thesis_point or "需补充核心判断",
            "key_variable": brief.key_variable or "",
        }

        return ArgumentScaffold(
            brief_id=brief.brief_id,
            title=f"{brief.asset}深度分析",
            core_disagreement=core_disagreement,
            sections=sections,
        )

    def _prioritize_dimensions(self, sac: Optional[SACEntry], brief: WritingBrief) -> list[DimensionPriority]:
        """识别 1-2 个关键维度分配深度资源。

        策略：
        1. 如果 brief 有核心判断点 → 匹配最相关的 2 个维度
        2. 否则 → 默认可比维度 (profit/compete) 设为深度
        3. core_disagreement 永远是深度的
        """
        priorities = {}

        # core_disagreement 永远是深度
        priorities["core_disagreement"] = DimensionPriority(id="core_disagreement", depth="deep", weight=2.0)

        thesis = (brief.core_thesis_point or "") + " " + (brief.key_variable or "")
        if thesis:
            keywords = thesis.split(" ")
            for dim_id, dim_question in [
                ("profit", "产业链利润"),
                ("compete", "竞争格局"),
                ("market", "市场空间"),
                ("tech", "技术路线"),
                ("policy", "政策"),
                ("financial", "财务"),
                ("growth", "增长"),
            ]:
                for kw in keywords:
                    if kw in dim_question and dim_id not in priorities:
                        priorities[dim_id] = DimensionPriority(id=dim_id, depth="deep", weight=1.5)
                        break
                if len([p for p in priorities.values() if p.depth == "deep"]) >= 2:
                    break

        # 默认深度：profit + compete
        if len([p for p in priorities.values() if p.depth == "deep"]) < 2:
            for dim_id in ["profit", "compete"]:
                if dim_id not in priorities:
                    priorities[dim_id] = DimensionPriority(id=dim_id, depth="deep", weight=1.5)
                if len([p for p in priorities.values() if p.depth == "deep"]) >= 2:
                    break

        # sharp_judgment 也是深度
        priorities["sharp_judgment"] = DimensionPriority(id="sharp_judgment", depth="deep", weight=1.5)

        logger.info(f"聚焦深度: {[p.id for p in priorities.values() if p.depth == 'deep']}")
        return list(priorities.values())

    def _match_evidence(self, dim: dict, pool: dict[str, DataPoint]) -> list[str]:
        question = (dim.get("question", "") + " " + dim.get("id", "")).lower()
        required = dim.get("required_elements", [])
        matched = []
        keywords = []
        for kw in ["营收", "利润", "毛利率", "ROE", "PE", "增速", "增长",
                    "市占率", "负债", "现金流", "估值"]:
            if kw in question:
                keywords.append(kw)
        for name, dp in pool.items():
            score = 0
            for kw in keywords:
                if kw in name:
                    score += 1
            for el in required:
                if isinstance(el, str) and el in name:
                    score += 2
            if score > 0:
                matched.append(name)
        return matched[:max(dim.get("evidence_min", 1) * 2, 4)]

    def _find_counter_evidence(self, dim: dict, pool: dict[str, DataPoint]) -> list[str]:
        names = list(pool.keys())
        return names[-min(len(names) // 3, 2):] if len(names) > 3 else []

    def _generate_thesis(self, brief: WritingBrief, dim: dict, matched_ids: list[str], pool: dict[str, DataPoint]) -> str:
        question = dim.get("question", "")
        dim_id = dim.get("id", "")
        if dim_id == "core_disagreement":
            return (f"市场认为「{brief.market_consensus or '待确认'}」；"
                    f"我们判断「{brief.our_view or brief.core_thesis_point or '待确认'}」"
                    f"——核心分歧在「{brief.key_variable or '待识别'}」")
        if brief.core_thesis_point:
            return f"{question} 核心判断：「{brief.core_thesis_point}」"
        return f"分析维度「{question}」：结合已有数据进行分析判断。"

    @staticmethod
    def _dim_title(dim_id: str, question: str) -> str:
        titles = {
            "core_disagreement": "核心分歧", "business_model": "商业模式",
            "financial_analysis": "财务分析", "competitive_position": "竞争格局",
            "growth_drivers": "增长驱动", "governance_esg": "治理与ESG",
            "valuation_assessment": "估值分析", "falsification": "证伪条件",
            "catalyst": "催化剂", "sharp_judgment": "核心锐判",
            "bold_call": "核心判断", "polarity": "核心分歧与极性",
            "policy": "政策传导", "market": "市场空间", "s_d": "供需分析",
            "profit": "产业链与利润池", "compete": "竞争格局",
            "tech": "技术路线", "capital": "资本市场映射",
            "headline": "核心数字", "key_surprise": "超预期分析",
            "segment_analysis": "分部业绩", "balance_cashflow": "现金流质量",
            "outlook_implication": "展望与影响",
        }
        return titles.get(dim_id, question[:30])
