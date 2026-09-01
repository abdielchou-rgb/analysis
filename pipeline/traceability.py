"""
pipeline/traceability.py — 溯源链 + 可审计性

1. 每个观点链接到具体数据和推理过程
2. 支持溯源查询（从结论追溯到数据源）
3. 支持审计日志（记录每个决策点）
4. 支持置信度校准（基于证据质量）
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.traceability")

_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class DataSource:
    """数据源"""

    name: str
    type: str  # akshare/tavily/yfinance/knowledge/compute
    url: str = ""
    timestamp: float = field(default_factory=time.time)
    reliability: float = 0.8  # 可靠性 0-1


@dataclass
class ReasoningStep:
    """推理步骤"""

    step_id: int
    description: str
    input_data: list[str] = field(default_factory=list)
    output: str = ""
    confidence: float = 0.0
    duration_ms: float = 0.0


@dataclass
class Claim:
    """观点/结论"""

    claim_id: str
    content: str
    claim_type: str = ""  # judgment/prediction/assessment
    confidence: float = 0.0
    data_sources: list[DataSource] = field(default_factory=list)
    reasoning_steps: list[ReasoningStep] = field(default_factory=list)
    falsification_conditions: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AuditTrail:
    """审计轨迹"""

    claims: list[Claim] = field(default_factory=list)
    total_duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


class TraceabilityEngine:
    """
    溯源链 + 可审计性引擎

    核心机制：
    1. 每个观点链接到具体数据和推理过程
    2. 支持溯源查询（从结论追溯到数据源）
    3. 支持审计日志（记录每个决策点）
    4. 支持置信度校准（基于证据质量）
    """

    def __init__(self, output_dir: Optional[str] = None):
        """
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir or str(_ROOT / "output")
        self._claims: list[Claim] = []
        self._data_sources: list[DataSource] = []
        self._reasoning_steps: list[ReasoningStep] = []
        self._step_counter = 0

    def add_claim(
        self,
        claim_id: str,
        content: str,
        claim_type: str = "judgment",
        confidence: float = 0.0,
        data_sources: Optional[list[DataSource]] = None,
        falsification_conditions: Optional[list[str]] = None,
    ) -> Claim:
        """
        添加观点

        Args:
            claim_id: 观点ID
            content: 观点内容
            claim_type: 观点类型
            confidence: 置信度
            data_sources: 数据源
            falsification_conditions: 证伪条件

        Returns:
            Claim: 观点对象
        """
        claim = Claim(
            claim_id=claim_id,
            content=content,
            claim_type=claim_type,
            confidence=confidence,
            data_sources=data_sources or [],
            falsification_conditions=falsification_conditions or [],
        )
        self._claims.append(claim)
        return claim

    def add_data_source(
        self,
        name: str,
        source_type: str,
        url: str = "",
        reliability: float = 0.8,
    ) -> DataSource:
        """
        添加数据源

        Args:
            name: 数据源名称
            source_type: 数据源类型
            url: 数据源URL
            reliability: 可靠性

        Returns:
            DataSource: 数据源对象
        """
        source = DataSource(
            name=name,
            type=source_type,
            url=url,
            reliability=reliability,
        )
        self._data_sources.append(source)
        return source

    def add_reasoning_step(
        self,
        description: str,
        input_data: Optional[list[str]] = None,
        output: str = "",
        confidence: float = 0.0,
    ) -> ReasoningStep:
        """
        添加推理步骤

        Args:
            description: 步骤描述
            input_data: 输入数据
            output: 输出
            confidence: 置信度

        Returns:
            ReasoningStep: 推理步骤对象
        """
        self._step_counter += 1
        step = ReasoningStep(
            step_id=self._step_counter,
            description=description,
            input_data=input_data or [],
            output=output,
            confidence=confidence,
        )
        self._reasoning_steps.append(step)
        return step

    def link_claim_to_data(self, claim_id: str, data_source: DataSource) -> bool:
        """
        链接观点到数据源

        Args:
            claim_id: 观点ID
            data_source: 数据源

        Returns:
            bool: 是否成功
        """
        for claim in self._claims:
            if claim.claim_id == claim_id:
                claim.data_sources.append(data_source)
                return True
        return False

    def link_claim_to_reasoning(self, claim_id: str, reasoning_step: ReasoningStep) -> bool:
        """
        链接观点到推理步骤

        Args:
            claim_id: 观点ID
            reasoning_step: 推理步骤

        Returns:
            bool: 是否成功
        """
        for claim in self._claims:
            if claim.claim_id == claim_id:
                claim.reasoning_steps.append(reasoning_step)
                return True
        return False

    def trace_claim(self, claim_id: str) -> Optional[dict]:
        """
        溯源观点

        Args:
            claim_id: 观点ID

        Returns:
            dict: 溯源结果
        """
        for claim in self._claims:
            if claim.claim_id == claim_id:
                return {
                    "claim": {
                        "id": claim.claim_id,
                        "content": claim.content,
                        "type": claim.claim_type,
                        "confidence": claim.confidence,
                    },
                    "data_sources": [
                        {
                            "name": ds.name,
                            "type": ds.type,
                            "reliability": ds.reliability,
                        }
                        for ds in claim.data_sources
                    ],
                    "reasoning_steps": [
                        {
                            "id": rs.step_id,
                            "description": rs.description,
                            "input": rs.input_data,
                            "output": rs.output,
                            "confidence": rs.confidence,
                        }
                        for rs in claim.reasoning_steps
                    ],
                    "falsification_conditions": claim.falsification_conditions,
                }
        return None

    def generate_audit_trail(self) -> AuditTrail:
        """
        生成审计轨迹

        Returns:
            AuditTrail: 审计轨迹
        """
        trail = AuditTrail(
            claims=self._claims.copy(),
            metadata={
                "total_claims": len(self._claims),
                "total_data_sources": len(self._data_sources),
                "total_reasoning_steps": len(self._reasoning_steps),
            },
        )
        return trail

    def export_to_json(self, filepath: Optional[str] = None) -> str:
        """
        导出为 JSON

        Args:
            filepath: 文件路径

        Returns:
            str: JSON 字符串
        """
        data = {
            "claims": [
                {
                    "id": c.claim_id,
                    "content": c.content,
                    "type": c.claim_type,
                    "confidence": c.confidence,
                    "data_sources": [
                        {"name": ds.name, "type": ds.type, "reliability": ds.reliability} for ds in c.data_sources
                    ],
                    "reasoning_steps": [
                        {
                            "id": rs.step_id,
                            "description": rs.description,
                            "output": rs.output,
                            "confidence": rs.confidence,
                        }
                        for rs in c.reasoning_steps
                    ],
                    "falsification_conditions": c.falsification_conditions,
                }
                for c in self._claims
            ],
            "data_sources": [
                {"name": ds.name, "type": ds.type, "reliability": ds.reliability} for ds in self._data_sources
            ],
            "reasoning_steps": [
                {
                    "id": rs.step_id,
                    "description": rs.description,
                    "input": rs.input_data,
                    "output": rs.output,
                    "confidence": rs.confidence,
                }
                for rs in self._reasoning_steps
            ],
        }

        json_str = json.dumps(data, ensure_ascii=False, indent=2)

        if filepath:
            Path(filepath).write_text(json_str, encoding="utf-8")

        return json_str

    def calculate_overall_confidence(self) -> float:
        """
        计算整体置信度

        Returns:
            float: 整体置信度
        """
        if not self._claims:
            return 0.0

        # 加权平均（基于数据源可靠性）
        total_weight = 0.0
        weighted_confidence = 0.0

        for claim in self._claims:
            # 数据源可靠性加权
            source_reliability = 1.0
            if claim.data_sources:
                avg_reliability = sum(ds.reliability for ds in claim.data_sources) / len(claim.data_sources)
                source_reliability = avg_reliability

            weight = source_reliability
            total_weight += weight
            weighted_confidence += claim.confidence * weight

        return weighted_confidence / total_weight if total_weight > 0 else 0.5

    # ═══ 增强溯源机制 ═══

    def generate_audit_report(self) -> dict:
        """
        生成完整审计报告

        Returns:
            dict: 审计报告
        """
        report = {
            "summary": {
                "total_claims": len(self._claims),
                "total_data_sources": len(self._data_sources),
                "total_reasoning_steps": len(self._reasoning_steps),
                "overall_confidence": self.calculate_overall_confidence(),
            },
            "claims": [],
            "data_sources": [],
            "reasoning_chain": [],
        }

        # 观点详情
        for claim in self._claims:
            claim_detail = {
                "id": claim.claim_id,
                "content": claim.content,
                "type": claim.claim_type,
                "confidence": claim.confidence,
                "data_sources": [
                    {
                        "name": ds.name,
                        "type": ds.type,
                        "reliability": ds.reliability,
                    }
                    for ds in claim.data_sources
                ],
                "reasoning_steps": [
                    {
                        "id": rs.step_id,
                        "description": rs.description,
                        "output": rs.output,
                        "confidence": rs.confidence,
                    }
                    for rs in claim.reasoning_steps
                ],
                "falsification_conditions": claim.falsification_conditions,
            }
            report["claims"].append(claim_detail)

        # 数据源详情
        for ds in self._data_sources:
            ds_detail = {
                "name": ds.name,
                "type": ds.type,
                "reliability": ds.reliability,
                "url": ds.url,
            }
            report["data_sources"].append(ds_detail)

        # 推理链
        for rs in self._reasoning_steps:
            rs_detail = {
                "id": rs.step_id,
                "description": rs.description,
                "input": rs.input_data,
                "output": rs.output,
                "confidence": rs.confidence,
            }
            report["reasoning_chain"].append(rs_detail)

        return report

    def calibrate_confidence(self) -> dict:
        """
        置信度校准

        基于证据质量校准置信度

        Returns:
            dict: 校准结果
        """
        calibration_results = []

        for claim in self._claims:
            # 原始置信度
            original_confidence = claim.confidence

            # 基于数据源质量调整
            source_quality = 1.0
            if claim.data_sources:
                avg_reliability = sum(ds.reliability for ds in claim.data_sources) / len(claim.data_sources)
                source_quality = avg_reliability

            # 基于推理步骤数量调整
            reasoning_depth = min(1.0, len(claim.reasoning_steps) / 3.0)

            # 基于证伪条件完整性调整
            falsification_completeness = min(1.0, len(claim.falsification_conditions) / 2.0)

            # 综合校准
            calibrated_confidence = (
                original_confidence * 0.4
                + source_quality * 0.3
                + reasoning_depth * 0.2
                + falsification_completeness * 0.1
            )

            calibration_results.append(
                {
                    "claim_id": claim.claim_id,
                    "original_confidence": original_confidence,
                    "calibrated_confidence": calibrated_confidence,
                    "source_quality": source_quality,
                    "reasoning_depth": reasoning_depth,
                    "falsification_completeness": falsification_completeness,
                }
            )

            # 更新置信度
            claim.confidence = calibrated_confidence

        return {
            "calibration_results": calibration_results,
            "overall_confidence": self.calculate_overall_confidence(),
        }

    def trace_to_source(self, claim_id: str) -> dict:
        """
        从观点追溯到数据源

        Args:
            claim_id: 观点ID

        Returns:
            dict: 溯源结果
        """
        for claim in self._claims:
            if claim.claim_id == claim_id:
                return {
                    "claim": {
                        "id": claim.claim_id,
                        "content": claim.content,
                        "confidence": claim.confidence,
                    },
                    "data_sources": [
                        {
                            "name": ds.name,
                            "type": ds.type,
                            "reliability": ds.reliability,
                            "url": ds.url,
                        }
                        for ds in claim.data_sources
                    ],
                    "reasoning_chain": [
                        {
                            "step": rs.step_id,
                            "description": rs.description,
                            "input": rs.input_data,
                            "output": rs.output,
                        }
                        for rs in claim.reasoning_steps
                    ],
                }

        return {"error": f"Claim {claim_id} not found"}
