"""
Decimal 精度注册表 — 所有 engine/ 计算模块从此处导入精度工具。
确保全局 Decimal 上下文一致性。

用法:
    from engine.precision_registry import D, dsum, dmul, ddiv, dfmt, PreciseValuation
"""

from engine.precision import (
    D,
    PreciseValuation,
    ddiv,
    dfmt,
    dpct,
    dsum,
    dto_float,
)

__all__ = [
    "D",
    "PreciseValuation",
    "ddiv",
    "dfmt",
    "dpct",
    "dsum",
    "dto_float",
]
