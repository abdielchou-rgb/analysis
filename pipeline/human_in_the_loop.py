"""
pipeline/human_in_the_loop.py — Human-in-the-loop + 决策支持

1. 关键决策点人工确认
2. 支持人工干预和修正
3. 支持决策建议（基于分析结果）
4. 支持决策记录（记录人工决策）
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("2hao.human_in_the_loop")

_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class DecisionPoint:
    """决策点"""

    point_id: str
    description: str
    options: list[str] = field(default_factory=list)
    recommendation: str = ""
    confidence: float = 0.0
    requires_human: bool = True
    human_decision: str = ""
    human_reason: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class Intervention:
    """人工干预"""

    intervention_id: str
    target: str  # 干预目标（如：某个观点、某个数据）
    action: str  # 干预动作（如：修正、删除、补充）
    original_value: str = ""
    new_value: str = ""
    reason: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class DecisionRecord:
    """决策记录"""

    decision_id: str
    decision_point: DecisionPoint
    final_decision: str
    decision_maker: str = "human"  # human/ai/hybrid
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)


class HumanInTheLoop:
    """
    Human-in-the-loop + 决策支持

    核心机制：
    1. 关键决策点人工确认
    2. 支持人工干预和修正
    3. 支持决策建议（基于分析结果）
    4. 支持决策记录（记录人工决策）
    """

    def __init__(self, output_dir: Optional[str] = None):
        """
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir or str(_ROOT / "output")
        self._decision_points: list[DecisionPoint] = []
        self._interventions: list[Intervention] = []
        self._decision_records: list[DecisionRecord] = []

    def add_decision_point(
        self,
        point_id: str,
        description: str,
        options: list[str],
        recommendation: str = "",
        confidence: float = 0.0,
        requires_human: bool = True,
    ) -> DecisionPoint:
        """
        添加决策点

        Args:
            point_id: 决策点ID
            description: 描述
            options: 选项列表
            recommendation: 推荐选项
            confidence: 推荐置信度
            requires_human: 是否需要人工确认

        Returns:
            DecisionPoint: 决策点对象
        """
        point = DecisionPoint(
            point_id=point_id,
            description=description,
            options=options,
            recommendation=recommendation,
            confidence=confidence,
            requires_human=requires_human,
        )
        self._decision_points.append(point)
        return point

    def record_human_decision(
        self,
        point_id: str,
        decision: str,
        reason: str = "",
    ) -> Optional[DecisionRecord]:
        """
        记录人工决策

        Args:
            point_id: 决策点ID
            decision: 决策
            reason: 原因

        Returns:
            DecisionRecord: 决策记录
        """
        for point in self._decision_points:
            if point.point_id == point_id:
                point.human_decision = decision
                point.human_reason = reason

                record = DecisionRecord(
                    decision_id=f"decision_{len(self._decision_records) + 1}",
                    decision_point=point,
                    final_decision=decision,
                    decision_maker="human",
                    confidence=point.confidence,
                )
                self._decision_records.append(record)
                return record

        return None

    def add_intervention(
        self,
        target: str,
        action: str,
        original_value: str = "",
        new_value: str = "",
        reason: str = "",
    ) -> Intervention:
        """
        添加人工干预

        Args:
            target: 干预目标
            action: 干预动作
            original_value: 原始值
            new_value: 新值
            reason: 原因

        Returns:
            Intervention: 干预对象
        """
        intervention = Intervention(
            intervention_id=f"intervention_{len(self._interventions) + 1}",
            target=target,
            action=action,
            original_value=original_value,
            new_value=new_value,
            reason=reason,
        )
        self._interventions.append(intervention)
        return intervention

    def get_pending_decisions(self) -> list[DecisionPoint]:
        """
        获取待决策点

        Returns:
            list[DecisionPoint]: 待决策点列表
        """
        return [
            point for point in self._decision_points
            if point.requires_human and not point.human_decision
        ]

    def get_decision_recommendation(
        self,
        point_id: str,
        context: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        获取决策建议

        Args:
            point_id: 决策点ID
            context: 上下文

        Returns:
            dict: 决策建议
        """
        for point in self._decision_points:
            if point.point_id == point_id:
                return {
                    "point_id": point.point_id,
                    "description": point.description,
                    "options": point.options,
                    "recommendation": point.recommendation,
                    "confidence": point.confidence,
                    "context": context,
                }
        return None

    def generate_decision_report(self) -> dict:
        """
        生成决策报告

        Returns:
            dict: 决策报告
        """
        return {
            "decision_points": [
                {
                    "id": dp.point_id,
                    "description": dp.description,
                    "options": dp.options,
                    "recommendation": dp.recommendation,
                    "confidence": dp.confidence,
                    "requires_human": dp.requires_human,
                    "human_decision": dp.human_decision,
                    "human_reason": dp.human_reason,
                }
                for dp in self._decision_points
            ],
            "interventions": [
                {
                    "id": iv.intervention_id,
                    "target": iv.target,
                    "action": iv.action,
                    "original_value": iv.original_value,
                    "new_value": iv.new_value,
                    "reason": iv.reason,
                }
                for iv in self._interventions
            ],
            "decision_records": [
                {
                    "id": dr.decision_id,
                    "point_id": dr.decision_point.point_id,
                    "final_decision": dr.final_decision,
                    "decision_maker": dr.decision_maker,
                    "confidence": dr.confidence,
                }
                for dr in self._decision_records
            ],
            "summary": {
                "total_decision_points": len(self._decision_points),
                "pending_decisions": len(self.get_pending_decisions()),
                "total_interventions": len(self._interventions),
                "total_decisions": len(self._decision_records),
            },
        }

    def export_to_json(self, filepath: Optional[str] = None) -> str:
        """
        导出为 JSON

        Args:
            filepath: 文件路径

        Returns:
            str: JSON 字符串
        """
        report = self.generate_decision_report()
        json_str = json.dumps(report, ensure_ascii=False, indent=2)

        if filepath:
            Path(filepath).write_text(json_str, encoding="utf-8")

        return json_str
