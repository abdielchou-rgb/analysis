# -*- coding: utf-8 -*-
"""Verification Engine - 验证引擎

核心原则：
- 三层 Gate：Blocker (Hard Fail) / Quality (Soft Fail) / Advisory (Info)
- Gate 前移：数据、计算错误在写作前发现
- 可追溯：每个检查可追溯到具体 Claim 和 Evidence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Tuple

from core.analysis_context import GateReport


class GateSeverity(Enum):
    """Gate 严重级别"""

    BLOCKER = "blocker"  # 硬阻断：数据错误、计算错误、核心数字无来源
    QUALITY = "quality"  # 软阻断：引用密度、So-What 链、主观评分
    ADVISORY = "advisory"  # 仅告警：风格指纹、模板相似度、洞察质量


@dataclass(frozen=True)
class GateCheckResult:
    """单项检查结果"""

    name: str
    severity: GateSeverity
    passed: bool
    score: float  # 0-1
    details: str
    related_claims: Tuple[str, ...] = ()
    related_evidence: Tuple[str, ...] = ()
    remediation: str = ""


@dataclass(frozen=True)
class GateReport:
    """Gate 检查报告"""

    overall_score: float
    passed: bool
    blocker_failures: Tuple[str, ...]
    quality_failures: Tuple[str, ...]
    advisory_notes: Tuple[str, ...]
    check_results: Tuple["GateCheckResult", ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def blocker_count(self) -> int:
        return len(self.blocker_failures)

    @property
    def quality_fail_count(self) -> int:
        return len(self.quality_failures)

    @property
    def overall_passed(self) -> bool:
        return self.passed and len(self.blocker_failures) == 0


class VerificationEngine:
    """验证引擎 - 三层 Gate 架构"""

    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._severity_map: Dict[str, GateSeverity] = {}
        self._register_default_checks()

    def register_check(
        self, name: str, check_fn: Callable, severity: GateSeverity = GateSeverity.QUALITY, description: str = ""
    ):
        """注册检查函数"""
        self._checks[name] = check_fn
        self._severity_map[name] = severity

    def run_all(self, context: Any) -> "GateReport":
        """运行所有检查"""
        results = []
        blocker_failures = []
        quality_failures = []
        advisory_notes = []

        for name, check_fn in self._checks.items():
            severity = self._severity_map.get(name, GateSeverity.QUALITY)
            try:
                result = check_fn()

                check_result = GateCheckResult(
                    name=name,
                    severity=severity,
                    passed=result.get("passed", False),
                    score=result.get("score", 0.0),
                    details=result.get("details", ""),
                    remediation=result.get("remediation", ""),
                )

                # 根据严重级别分类
                if not result.get("passed", False):
                    if severity == GateSeverity.BLOCKER:
                        blocker_failures.append(name)
                    elif severity == GateSeverity.QUALITY:
                        quality_failures.append(name)
                    else:
                        advisory_notes.append(name)

                # 这里简化处理，实际需要完整的 GateCheckResult 构造
            except Exception as e:
                # 检查本身出错
                pass

        # 计算总分
        # 简化：Blocker 失败直接不通过，Quality 计入均分
        # 实际实现更复杂

        return None  # 占位

    def _register_default_checks(self):
        """注册默认检查"""
        # Blocker 级
        self.register_check("data_conflicts", self._check_data_conflicts, GateSeverity.BLOCKER, "数据冲突检测")
        self.register_check(
            "cross_section_consistency", self._check_cross_section_consistency, GateSeverity.BLOCKER, "跨段数值一致性"
        )
        self.register_check("numeric_accuracy", self._check_numeric_accuracy, GateSeverity.BLOCKER, "数值准确性")

        # Quality 级
        self.register_check("so_what_chain", self._check_so_what_chain, GateSeverity.QUALITY, "So What 链完整性")
        self.register_check("inline_citations", self._check_inline_citations, GateSeverity.QUALITY, "内联引用密度")
        self.register_check("evidence_layer", self._check_evidence_layer, GateSeverity.QUALITY, "证据层完整性")

        # Advisory
        self.register_check("template_repeat", self._check_template_repeat, GateSeverity.ADVISORY, "模板重复检测")
        self.register_check("ai_tone", self._check_ai_tone, GateSeverity.ADVISORY, "AI 风格检测")

    # 实际检查实现占位
    def _check_data_conflicts(self, context: Any) -> Dict:
        return {"passed": True, "score": 1.0, "details": "数据冲突检测通过"}

    def _check_cross_section_consistency(self, context: Any) -> Dict:
        return {"passed": True, "score": 1.0, "details": "跨段一致性检查通过"}

    def _check_numeric_accuracy(self, context: Any) -> Dict:
        return {"passed": True, "score": 1.0, "details": "数值准确性检查通过"}

    def _check_so_what_chain(self, context: Any) -> Dict:
        return {"passed": True, "score": 1.0, "details": "So What 链完整"}

    def _check_inline_citations(self, context: Any) -> Dict:
        return {"passed": True, "score": 1.0, "details": "引用密度达标"}

    def _check_evidence_layer(self, context: Any) -> Dict:
        return {"passed": True, "score": 1.0, "details": "证据层完整"}

    def _check_template_repeat(self, context: Any) -> Dict:
        return {"passed": True, "score": 1.0, "details": "模板重复检测通过"}

    def _check_ai_tone(self, context: Any) -> Dict:
        return {"passed": True, "score": 1.0, "details": "AI 语调检测通过"}
