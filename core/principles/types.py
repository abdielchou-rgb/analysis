# -*- coding: utf-8 -*-
"""First Principle Contract: 数值类型系统

核心原则：任何进入计算系统的数字必须带来源与状态。
杜绝 Silent Business Defaults（data.get("key", 50000) 这类写法）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, Tuple


class DataState(Enum):
    """数值的来源状态"""
    OBSERVED = "observed"      # 直接观测到的事实（财报、公告、监管数据）
    DERIVED = "derived"        # 由计算推导得出（DCF、可比法、毛利率拆解等）
    ASSUMPTION = "assumption"  # 显式假设（需用户确认或场景设定）
    SCENARIO = "scenario"      # 情景推演（悲观/基准/乐观情景）
    MISSING = "missing"        # 真实缺失，无法获取、无法合理假设


@dataclass(frozen=True)
class Value:
    """带来源与状态的数值原语

    所有进入计算系统的数字必须包装为 Value 对象。
    禁止裸数字在计算链中流转。
    """
    value: Optional[float]
    state: DataState
    source: str                    # 来源标识（如 "2025 Annual Report", "DCF_Model_v3"）
    confidence: float = 1.0        # 置信度 [0, 1]
    formula: Optional[str] = None  # 推导公式（如 "net_income / revenue"）
    parents: Tuple = ()            # 父节点 Value 引用（用于溯源）

    def __post_init__(self):
        if self.value is not None and not isinstance(self.value, (int, float)):
            raise TypeError(f"Value.value must be numeric, got {type(self.value)}")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")

    @property
    def is_usable(self) -> bool:
        """是否可用于计算"""
        return self.value is not None and self.state != DataState.MISSING

    def __float__(self):
        if not self.is_usable:
            raise ValueError(f"Cannot convert {self.state} value to float")
        return float(self.value)

    def __add__(self, other: "Value") -> "Value":
        if not (self.is_usable and other.is_usable):
            return Value(None, DataState.MISSING, f"{self.source}+{other.source}")
        return Value(
            value=self.value + other.value,
            state=DataState.DERIVED,
            source=f"{self.source}+{other.source}",
            confidence=min(self.confidence, other.confidence),
            formula=f"({self.formula or self.value}) + ({other.formula or other.value})",
            parents=(self, other)
        )

    def __mul__(self, other: "Value") -> "Value":
        if not (self.is_usable and other.is_usable):
            return Value(None, DataState.MISSING, f"{self.source}*{other.source}")
        return Value(
            value=self.value * other.value,
            state=DataState.DERIVED,
            source=f"{self.source}*{other.source}",
            confidence=min(self.confidence, other.confidence),
            formula=f"({self.formula or self.value}) * ({other.formula or other.value})",
            parents=(self, other)
        )

    def __truediv__(self, other: "Value") -> "Value":
        if not (self.is_usable and other.is_usable) or other.value == 0:
            return Value(None, DataState.MISSING, f"{self.source}/{other.source}")
        return Value(
            value=self.value / other.value,
            state=DataState.DERIVED,
            source=f"{self.source}/{other.source}",
            confidence=min(self.confidence, other.confidence),
            formula=f"({self.formula or self.value}) / ({other.formula or other.value})",
            parents=(self, other)
        )


def require_value(data: dict, key: str, source: str) -> Value:
    """强制获取数值，缺失时抛出异常或返回 MISSING Value"""
    if key in data and data[key] is not None:
        try:
            return Value(
                value=float(data[key]),
                state=DataState.OBSERVED,
                source=source,
                confidence=1.0
            )
        except (TypeError, ValueError):
            pass
    return Value(
        value=None,
        state=DataState.MISSING,
        source=f"{source}.{key}"
    )


def assume_value(value: float, source: str, confidence: float = 0.5) -> Value:
    """显式创建假设值"""
    return Value(
        value=value,
        state=DataState.ASSUMPTION,
        source=source,
        confidence=confidence
    )


def scenario_value(value: float, scenario_name: str, source: str) -> Value:
    """显式创建情景值"""
    return Value(
        value=value,
        state=DataState.SCENARIO,
        source=f"{source}.scenario[{scenario_name}]",
        confidence=0.7
    )


def derive_value(
    value: float,
    formula: str,
    parents: Tuple[Value, ...],
    source: str,
    confidence: float = 0.9
) -> Value:
    """从计算推导产生数值"""
    return Value(
        value=value,
        state=DataState.DERIVED,
        source=source,
        confidence=confidence,
        formula=formula,
        parents=parents
    )