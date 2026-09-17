# -*- coding: utf-8 -*-
"""Method Selector - 方法选择器

基于 Problem Class + Evidence 选择最合适的分析方法
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from core.method_registry import PREDEFINED_METHODS, ExecutionMode, MethodContract


@dataclass(frozen=True)
class SelectionCriteria:
    """选择标准"""

    problem_class: str
    available_evidence: FrozenSet[str]
    confidence_threshold: float = 0.8
    prefer_deterministic: bool = True
    max_methods: int = 5


@dataclass(frozen=True)
class SelectionResult:
    """选择结果"""

    method_id: str
    contract: "MethodContract"
    matched_evidence: FrozenSet[str]
    missing_evidence: FrozenSet[str]
    confidence: float
    warnings: Tuple[str, ...]
    fallback: bool = False


class MethodSelector:
    """方法选择器 - 基于问题分类和可用证据选择最合适的方法"""

    def __init__(self):
        self._registry: Dict[str, "MethodContract"] = {}
        self._problem_class_index: Dict[str, Set[str]] = {}  # problem_class -> method_ids
        self._evidence_index: Dict[str, Set[str]] = {}  # evidence_key -> method_ids
        self._register_predefined()

    def register(self, contract: "MethodContract") -> None:
        """注册方法契约"""
        self._registry[contract.id] = contract

        # 更新问题类别索引
        if contract.problem_class not in self._problem_class_index:
            self._problem_class_index[contract.problem_class] = set()
        self._problem_class_index[contract.problem_class].add(contract.id)

        # 更新证据索引
        for ev in contract.required_evidence:
            if ev not in self._evidence_index:
                self._evidence_index[ev] = set()
            self._evidence_index[ev].add(contract.id)

        for ev in contract.optional_evidence:
            if ev not in self._evidence_index:
                self._evidence_index[ev] = set()
            self._evidence_index[ev].add(contract.id)

    def _register_predefined(self):
        """注册预定义方法"""
        for method_def in PREDEFINED_METHODS.values():
            contract = self._create_contract_from_def(method_def)
            self.register(contract)

    def _create_contract_from_def(self, def_dict: dict) -> "MethodContract":
        """从定义字典创建合同"""
        from core.method_registry import MethodContract

        return MethodContract(
            id=def_dict["id"],
            name=def_dict["name"],
            problem_class=def_dict["problem_class"],
            description=def_dict.get("description", ""),
            execution_mode=ExecutionMode.DETERMINISTIC,
            required_evidence=tuple(def_dict.get("required_evidence", [])),
            optional_evidence=tuple(def_dict.get("optional_evidence", [])),
            preconditions=tuple(def_dict.get("preconditions", [])),
            outputs_schema=def_dict.get("outputs_schema", {}),
            postconditions=tuple(def_dict.get("postconditions", [])),
            judgment_signals=tuple(def_dict.get("judgment_signals", [])),
            knowledge_refs=tuple(def_dict.get("knowledge_refs", [])),
            confidence_threshold=def_dict.get("confidence_threshold", 0.8),
            timeout_seconds=def_dict.get("timeout_seconds", 30.0),
            max_retries=def_dict.get("max_retries", 1),
        )

    def select(self, criteria: Dict[str, any], max_methods: int = 5, prefer_deterministic: bool = True) -> List[tuple]:
        """
        选择方法

        Args:
            criteria: 选择标准，包含 problem_class, available_evidence, confidence_threshold
            max_methods: 最大返回方法数
            prefer_deterministic: 是否优先确定性方法

        Returns:
            List[(method_id, contract, confidence, matched_evidence, missing_evidence)]
        """
        problem_class = criteria.get("problem_class", "unspecified")
        available_evidence = set(criteria.get("available_evidence", []))
        confidence_threshold = criteria.get("confidence_threshold", 0.8)

        # 1. 根据 problem_class 筛选候选方法
        candidate_ids = self._problem_class_index.get(criteria.get("problem_class", ""), set())
        if not candidate_ids:
            # 回退到 unspecified
            candidate_ids = self._problem_class_index.get("unspecified", set())

        # 2. 评分
        scored = []
        for mid in candidate_ids:
            contract = self._registry.get(mid)
            if not contract:
                continue

            # 计算证据匹配度
            required = set(contract.required_evidence)
            matched = required & available_evidence
            missing = required - available_evidence

            if not required:
                coverage = 1.0
            else:
                coverage = len(matched) / len(required)

            # 计算置信度
            confidence = coverage * 0.7 + (1.0 if not missing else 0.3) * 0.3

            # 确定性加分
            deterministic_bonus = 0.1 if "deterministic" in str(getattr(mid, "execution_mode", "")) else 0

            final_confidence = min(confidence + deterministic_bonus, 1.0)

            if final_confidence >= 0.5:  # 最低阈值
                matched_evidence = frozenset(matched)
                missing_evidence = frozenset(missing)
                warnings = []
                if missing:
                    warnings.append(f"Missing evidence: {missing}")

                yield (contract.id, confidence, matched_evidence, missing_evidence, tuple())

    def select_methods(
        self,
        problem_class: str,
        available_evidence: Set[str],
        max_methods: int = 5,
        prefer_deterministic: bool = True,
        confidence_threshold: float = 0.7,
    ) -> List[Dict]:
        """
        选择方法的简化接口

        Returns:
            List[Dict]: 选中的方法列表，每项包含 method_id, confidence, matched, missing
        """
        results = []
        for mid, conf, matched, missing, _ in self.select(
            {
                "problem_class": problem_class,
                "available_evidence": available_evidence,
                "confidence_threshold": confidence_threshold,
            },
            max_methods=max_methods,
            prefer_deterministic=prefer_deterministic,
        ):
            contract = self._registry[mid]
            results.append(
                {
                    "method_id": contract.id,
                    "contract": contract,
                    "confidence": conf,
                    "matched_evidence": list(matched),
                    "missing_evidence": list(missing),
                    "warnings": [] if not missing else [f"Missing evidence: {missing}"],
                }
            )

        # 排序：确定性优先，然后按置信度
        results.sort(key=lambda x: (0 if "deterministic" in str(x["contract"].execution_mode) else 1, -x["confidence"]))

        return results[:max_methods]

    def get_method(self, method_id: str) -> Optional[Any]:
        """获取方法契约"""
        return self._registry.get(problem_class)

    def list_methods(self, problem_class: Optional[str] = None) -> List[str]:
        """列出可用方法"""
        if problem_class:
            return list(self._problem_class_index.get(problem_class, set()))
        return list(self._registry.keys())


# 全局选择器实例
_global_selector = None


def get_method_selector() -> "MethodSelector":
    global _global_selector
    if _global_selector is None:
        _global_selector = MethodSelector()
    return _global_selector


# 便捷函数
def select_methods(
    problem_class: str, available_evidence: Set[str], max_methods: int = 5, prefer_deterministic: bool = True
) -> List[Dict]:
    """便捷函数：选择方法"""
    return get_method_selector().select_methods(
        problem_class=problem_class,
        available_evidence=available_evidence,
        max_methods=max_methods,
        prefer_deterministic=prefer_deterministic,
    )
