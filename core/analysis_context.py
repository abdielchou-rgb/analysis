# -*- coding: utf-8 -*-
"""First Principle Contract: AnalysisContext v1

核心原则：AnalysisContext 是整个分析链的唯一事实源，不可变。
每次阶段推进产生新版本，保留父版本哈希，支持回溯、Diff、Replay、Rollback。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

from core.principles.types import DataState


class IntentType(Enum):
    LISTED_COMPANY = "listed_company"
    INDUSTRY_DEEP = "industry_deep"
    UNLISTED_COMPANY = "unlisted_company"
    EARNINGS_NOTES = "earnings_notes"
    DECISION_MEMO = "decision_memo"


class AnalysisMode(Enum):
    INTERACTIVE = "interactive"  # Workbench 交互模式
    BATCH = "batch"  # Pipeline 批量模式
    FAST = "fast"  # 快速模式（降级）
    DEGRADED = "degraded"  # 降级模式


@dataclass(frozen=True)
class Intent:
    """用户意图 - 不可变"""

    asset: str
    report_type: IntentType
    style: str = "cicc"
    mode: AnalysisMode = AnalysisMode.BATCH
    custom_requirements: FrozenSet[str] = field(default_factory=frozenset)
    client_questions: Tuple[str, ...] = field(default_factory=tuple)
    time_anchor: Optional[str] = None


@dataclass(frozen=True)
class EvidenceBundle:
    """证据包 - 不可变，只增不改"""

    raw_data: Mapping[str, Any] = field(default_factory=dict)
    chart_data: Mapping[str, Any] = field(default_factory=dict)
    data_dict: Mapping[str, Any] = field(default_factory=dict)
    data_sufficiency: Mapping[str, DataState] = field(default_factory=dict)
    provenance: Mapping[str, str] = field(default_factory=dict)  # key -> source

    def with_update(self, **kwargs) -> "EvidenceBundle":
        """返回新的 EvidenceBundle（函数式更新）"""
        return EvidenceBundle(
            raw_data={**self.raw_data, **kwargs.get("raw_data", {})},
            chart_data={**self.chart_data, **kwargs.get("chart_data", {})},
            data_dict={**self.data_dict, **kwargs.get("data_dict", {})},
            data_sufficiency={**self.data_sufficiency, **kwargs.get("data_sufficiency", {})},
            provenance={**self.provenance, **kwargs.get("provenance", {})},
        )


@dataclass(frozen=True)
class MethodSpec:
    """方法规约 - 方法选择的契约"""

    id: str
    problem_class: str
    required_evidence: FrozenSet[str]
    preconditions: Tuple[str, ...]
    postconditions: Tuple[str, ...]
    judgment_signals: FrozenSet[str]
    knowledge_refs: Tuple[str, ...]
    confidence_threshold: float = 0.8
    execution: str = "deterministic"  # deterministic / llm / hybrid


@dataclass(frozen=True)
class Finding:
    """分析发现 - 结构化、可验证、可溯源"""

    claim_id: str
    text: str
    section: str
    evidence: Tuple[Dict[str, Any], ...]
    method: str
    method_ref: str
    gate_passed: bool = False
    gate_checks: Mapping[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    version: int = 1


@dataclass(frozen=True)
class FindingStore:
    """发现仓库 - 单例，只增不改"""

    findings: Tuple[Finding, ...] = field(default_factory=tuple)

    def add(self, finding: Finding) -> "FindingStore":
        return FindingStore(findings=self.findings + (finding,))

    def get_by_section(self, section: str) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.section == section)

    def get_by_method(self, method: str) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.method == method)


@dataclass(frozen=True)
class SectionPlan:
    """章节计划"""

    section_id: str
    title: str
    required_findings: FrozenSet[str]
    dependencies: FrozenSet[str]  # 依赖的上游 section_id
    word_budget: int = 1500
    priority: int = 1


@dataclass(frozen=True)
class SectionPlanMap:
    """章节计划图"""

    plans: Mapping[str, SectionPlan] = field(default_factory=dict)

    def get_downstream(self, section_id: str) -> FrozenSet[str]:
        """获取下游依赖的 section"""
        downstream = set()
        for pid, plan in self.plans.items():
            if section_id in plan.dependencies:
                downstream.add(pid)
        return frozenset(downstream)


@dataclass(frozen=True)
class GateReport:
    """Gate 检查报告"""

    passed: bool
    score: float
    blocker_failures: Tuple[str, ...]
    quality_failures: Tuple[str, ...]
    advisory_notes: Tuple[str, ...]
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisContext:
    """分析上下文 - 不可变，版本化

    每次阶段推进产生新版本，保留父版本哈希。
    支持回溢、Diff、Replay、Rollback。
    """

    version: int
    parent_hash: str
    intent: Intent
    mode: AnalysisMode
    evidence: EvidenceBundle
    methods: Tuple[MethodSpec, ...]
    findings: FindingStore
    sections: Tuple[SectionPlan, ...]
    gate_results: Optional[GateReport] = None
    lineage: Mapping[str, Any] = field(default_factory=dict)
    performance: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def context_hash(self) -> str:
        """计算上下文哈希（用于版本标识）"""
        # 简化版：基于关键字段生成短哈希
        content = f"{self.version}:{self.intent.asset}:{self.intent.report_type.value}:{len(self.findings.findings)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def new_version(self, **updates) -> "AnalysisContext":
        """创建新版本（不可变更新）"""
        new_version = self.version + 1
        new_context = AnalysisContext(
            version=new_version,
            parent_hash=self.context_hash,
            intent=updates.get("intent", self.intent),
            mode=updates.get("mode", self.mode),
            evidence=updates.get("evidence", self.evidence),
            methods=updates.get("methods", self.methods),
            findings=updates.get("findings", self.findings),
            sections=updates.get("sections", self.sections),
            gate_results=updates.get("gate_results", self.gate_results),
            lineage=updates.get("lineage", self.lineage),
            performance=updates.get("performance", self.performance),
        )
        return new_context

    def rollback_to(self, target_version: int, history: List["AnalysisContext"]) -> "AnalysisContext":
        """回滚到指定版本"""
        for ctx in reversed(history):
            if ctx.version == target_version:
                return ctx
        raise ValueError(f"Version {target_version} not found in history")


# 默认 Section 依赖图
DEFAULT_SECTION_DEPS: FrozenSet[Tuple[str, str]] = frozenset(
    [
        ("valuation", "financial_analysis"),
        ("valuation", "competitive_position"),
        ("catalyst", "financial_analysis"),
        ("catalyst", "valuation"),
        ("risk", "financial_analysis"),
        ("risk", "valuation"),
        ("risk", "competitive_position"),
        ("conclusion", "valuation"),
        ("conclusion", "catalyst"),
        ("conclusion", "risk"),
        ("conclusion", "financial_analysis"),
    ]
)


def build_section_plan_map(report_type: str) -> SectionPlanMap:
    """根据报告类型构建章节计划图"""
    # 这里简化处理，实际应从 SAC YAML 加载
    base_plans = {
        "financial_analysis": SectionPlan("financial_analysis", "财务验证", frozenset(), frozenset()),
        "competitive_position": SectionPlan("competitive_position", "竞争格局", frozenset(), frozenset()),
        "valuation": SectionPlan(
            "valuation", "估值映射", frozenset(), frozenset({"financial_analysis", "competitive_position"})
        ),
        "catalyst": SectionPlan("catalyst", "催化剂", frozenset(), frozenset({"financial_analysis", "valuation"})),
        "risk": SectionPlan(
            "risk", "风险", frozenset(), frozenset({"financial_analysis", "valuation", "competitive_position"})
        ),
        "conclusion": SectionPlan(
            "conclusion", "投资建议", frozenset(), frozenset({"valuation", "catalyst", "risk", "financial_analysis"})
        ),
    }
    return SectionPlanMap(plans=base_plans)


# 验收：Context 树结构测试
if __name__ == "__main__":
    # 简单自测
    intent = Intent(asset="测试公司", report_type=IntentType.LISTED_COMPANY)
    evidence = EvidenceBundle()
    context = AnalysisContext(
        version=1,
        parent_hash="",
        intent=intent,
        mode=AnalysisMode.BATCH,
        evidence=evidence,
        methods=(),
        findings=FindingStore(),
        sections=(),
    )
    print(f"Context v1 created: {context.context_hash}")
    v2 = context.new_version(mode=AnalysisMode.FAST)
    print(f"Context v2 created: {v2.context_hash}, parent: {v2.parent_hash}")
    print("✅ AnalysisContext v1 结构自测通过")
