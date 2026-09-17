# -*- coding: utf-8 -*-
"""Finding Store - 发现仓库

核心原则：
- Claim 级谱系追踪：每个结论可溯源到 Evidence + Method + MKB
- 不可变存储：只增不改，版本化
- 支持查询：按 Section、Method、MKB、Claim ID 查询
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple


@dataclass(frozen=True)
class Claim:
    """原子级结论 - 知识谱系的最小单元"""

    claim_id: str
    text: str
    section: str
    evidence: Tuple[Dict[str, Any], ...]
    method: str
    method_ref: str
    mkb_refs: Tuple[str, ...] = field(default_factory=tuple)
    gate_passed: bool = False
    gate_checks: Mapping[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    version: int = 1

    @property
    def claim_hash(self) -> str:
        """Claim 唯一标识"""
        content = f"{self.text}:{self.section}:{self.method}:{self.method_ref}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class MethodExecution:
    """方法执行记录"""

    method_id: str
    method_name: str
    input_evidence: Tuple[str, ...]
    output_claims: Tuple[str, ...]  # claim_ids
    execution_time: float
    status: str  # success / failed / partial
    confidence: float
    errors: Tuple[str, ...] = field(default_factory=tuple)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class KnowledgeUsage:
    """知识使用记录"""

    knowledge_id: str  # MKB ID
    method_id: str
    section: str
    claim_ids: Tuple[str, ...]
    gate_passed: bool
    gate_score: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class ClaimLineage:
    """Claim 级谱系"""

    claim_id: str
    text: str
    section: str
    evidence: Tuple[Dict[str, Any], ...]
    method: str
    method_ref: str
    evidence_refs: Tuple[str, ...]  # evidence keys
    mkb_refs: Tuple[str, ...]  # MKB IDs
    gate_passed: bool
    gate_checks: Mapping[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    version: int = 1

    @property
    def lineage_hash(self) -> str:
        """谱系哈希"""
        content = f"{self.claim_id}:{self.method}:{self.method_ref}:{self.mkb_refs}"
        return hashlib.sha256(f"{content}:{self.text[:50]}".encode()).hexdigest()[:16]


class LineageTracker:
    """谱系追踪器 - 记录 Claim 级的完整谱系"""

    def __init__(self):
        self._claims: Dict[str, Claim] = {}
        self._method_executions: List[Any] = []
        self._knowledge_usages: List[Any] = []
        self._claim_lineages: Dict[str, Any] = {}
        self._section_claims: Dict[str, Set[str]] = {}  # section -> claim_ids
        self._method_claims: Dict[str, Set[str]] = {}  # method -> claim_ids
        self._mkb_claims: Dict[str, Set[str]] = {}  # mkb_id -> claim_ids
        self._evidence_claims: Dict[str, Set[str]] = {}  # evidence_key -> claim_ids
        self._claim_counter = 0

    def generate_claim_id(self) -> str:
        """生成唯一 Claim ID"""
        self._claim_counter += 1
        return f"C-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._claim_counter:04d}"

    def record_claim(
        self,
        text: str,
        section: str,
        evidence: Tuple[Dict[str, Any], ...],
        method: str,
        method_ref: str,
        mkb_refs: Tuple[str, ...] = (),
        gate_passed: bool = False,
        gate_checks: Mapping[str, str] = None,
    ) -> Claim:
        """记录一个 Claim"""
        claim_id = self.generate_claim_id()

        claim = Claim(
            claim_id=claim_id,
            text=text,
            section=section,
            evidence=evidence,
            method=method,
            method_ref=method_ref,
            mkb_refs=mkb_refs,
            gate_passed=gate_passed,
            gate_checks=gate_checks or {},
        )

        self._claims[claim.claim_id] = claim

        # 更新索引
        self._section_claims.setdefault(section, set()).add(claim.claim_id)
        self._method_claims.setdefault(method, set()).add(claim.claim_id)
        for mkb in mkb_refs:
            self._mkb_claims.setdefault(mkb, set()).add(claim.claim_id)
        for ev in evidence:
            for k in ev.keys():
                self._evidence_claims.setdefault(k, set()).add(claim.claim_id)

        return claim

    def record_method_execution(
        self,
        method_id: str,
        method_name: str,
        input_evidence: Tuple[str, ...],
        output_claims: Tuple[str, ...],
        execution_time: float,
        status: str,
        confidence: float,
        errors: Tuple[str, ...] = (),
    ) -> None:
        """记录方法执行"""
        exec_record = {
            "method_id": method_id,
            "method_name": method_id,
            "input_evidence": input_evidence,
            "output_claims": output_claims,
            "execution_time": execution_time,
            "status": status,
            "confidence": confidence,
            "errors": errors,
            "timestamp": datetime.now(),
        }
        # 存储到执行历史
        # TODO: 实现持久化

    def record_knowledge_usage(
        self,
        knowledge_id: str,
        method_id: str,
        section: str,
        claim_ids: Tuple[str, ...],
        gate_passed: bool,
        gate_score: float,
    ) -> None:
        """记录知识使用"""
        usage = {
            "knowledge_id": knowledge_id,
            "method_id": method_id,
            "section": section,
            "claim_ids": claim_ids,
            "gate_passed": gate_passed,
            "gate_score": gate_score,
            "timestamp": datetime.now(),
        }
        # TODO: 持久化

    def get_claim(self, claim_id: str) -> Optional[Any]:
        """获取 Claim"""
        return self._claims.get(claim_id)

    def get_claims_by_section(self, section: str) -> List[Any]:
        """获取章节下的所有 Claim"""
        claim_ids = self._section_claims.get(section, set())
        return [self._claims[cid] for cid in claim_ids if cid in self._claims]

    def get_claims_by_method(self, method: str) -> List[Any]:
        """获取方法产生的所有 Claim"""
        claim_ids = self._method_claims.get(method, set())
        return [self._claims[cid] for cid in claim_ids if cid in self._claims]

    def get_claims_by_mkb(self, mkb_id: str) -> List[Any]:
        """获取引用某 MKB 的所有 Claim"""
        claim_ids = self._mkb_claims.get(mkb_id, set())
        return [self._claims[cid] for cid in claim_ids if cid in self._claims]

    def get_claims_by_evidence(self, evidence_key: str) -> List[Any]:
        """获取引用某证据的所有 Claim"""
        claim_ids = self._evidence_claims.get(evidence_key, set())
        return [self._claims[cid] for cid in claim_ids if cid in self._claims]

    def build_claim_lineage(self, claim_id: str) -> Dict:
        """构建 Claim 完整谱系"""
        claim = self._claims.get(claim_id)
        if not claim:
            return {}

        return {
            "claim_id": claim.claim_id,
            "text": claim.text,
            "section": claim.section,
            "evidence": claim.evidence,
            "method": claim.method,
            "method_ref": claim.method_ref,
            "mkb_refs": list(claim.mkb_refs) if hasattr(claim, "mkb_refs") else [],
            "gate_passed": claim.gate_passed,
            "gate_checks": dict(claim.gate_checks) if claim.gate_checks else {},
            "created_at": claim.created_at.isoformat(),
            "version": claim.version,
            "lineage_hash": claim.claim_hash,
        }

    def get_method_stats(self, method_id: str) -> Dict:
        """获取方法使用统计"""
        claim_ids = self._method_claims.get(method_id, set())
        claims = [self._claims[cid] for cid in claim_ids if cid in self._claims]
        total = len(claims)
        passed = sum(1 for c in claims if c.gate_passed)
        return {
            "method_id": method_id,
            "total_claims": total,
            "passed": passed,
            "pass_rate": passed / total if total > 0 else 0,
            "claim_ids": list(claim_ids),
        }

    def get_mkb_effectiveness(self, mkb_id: str) -> Dict:
        """获取 MKB 有效性统计"""
        claim_ids = self._mkb_claims.get(mkb_id, set())
        claims = [self._claims[cid] for cid in claim_ids if cid in self._claims]
        total = len(claims)
        passed = sum(1 for c in claims if c.gate_passed)
        return {
            "mkb_id": mkb_id,
            "total_claims": total,
            "passed": passed,
            "pass_rate": passed / total if total > 0 else 0,
            "claim_ids": list(claim_ids),
        }

    def get_section_claims(self, section: str) -> List:
        """获取章节的所有 Claims"""
        return self.get_claims_by_section(section)

    def export_lineage(self) -> Dict:
        """导出完整谱系数据"""
        return {
            "claims": {cid: c.__dict__ for cid, c in self._claims.items()},
            "method_executions": [],
            "knowledge_usages": [],
            "exported_at": datetime.now().isoformat(),
        }


# 全局实例
_global_lineage_tracker = None


def get_lineage_tracker() -> "LineageTracker":
    global _global_lineage_tracker
    if _global_lineage_tracker is None:
        _global_lineage_tracker = LineageTracker()
    return _global_lineage_tracker
