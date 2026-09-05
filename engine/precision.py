"""
decimal.Decimal 精度层 — 全链路确定性计算，LLM 永不触碰四则运算。
参考 AlphaAnalyst: "Valuation is pure Python — decimal.Decimal everywhere."
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, getcontext
from typing import Any, List, Union

# 设置精度：50 位有效数字
getcontext().prec = 50
getcontext().rounding = ROUND_HALF_UP


def D(value: Union[str, int, float, Decimal]) -> Decimal:
    """快速创建 Decimal，兼容 float 输入和简单表达式"""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        # 简单表达式支持: "1500 * 0.65"
        try:
            return Decimal(value)
        except Exception:
            # 尝试计算简单表达式
            try:
                result = eval(value, {"__builtins__": {}}, {})
                return Decimal(str(result))
            except Exception:
                raise ValueError(f"无法转换为 Decimal: {value}")
    return Decimal(str(value))


def dsum(values: List[Union[str, int, float, Decimal]]) -> Decimal:
    """Decimal 求和"""
    return sum((D(v) for v in values), D(0))


def dmul(*values: Union[str, int, float, Decimal]) -> Decimal:
    """Decimal 乘法"""
    result = D(1)
    for v in values:
        result *= D(v)
    return result


def ddiv(
    numerator: Union[str, int, float, Decimal],
    denominator: Union[str, int, float, Decimal],
    default: Decimal = D(0),
) -> Decimal:
    """Decimal 除法（安全除零）"""
    d = D(denominator)
    if d == 0:
        return default
    return D(numerator) / d


def dpct(value: Decimal, decimals: int = 2) -> str:
    """Decimal 转百分比字符串"""
    return f"{value * 100:.{decimals}f}%"


def dfmt(value: Decimal, decimals: int = 2) -> str:
    """Decimal 格式化"""
    return f"{value:,.{decimals}f}"


def dto_float(value: Decimal) -> float:
    """Decimal → float（仅用于 Excel 导出等无法避免的场景）"""
    return float(value)


class PreciseValuation:
    """精确估值计算容器 — 所有中间值保留 Decimal"""

    def __init__(self):
        self._values: dict[str, Decimal] = {}
        self._sources: dict[str, str] = {}
        self._formulas: dict[str, str] = {}

    def set(self, key: str, value: Any, source: str = "", formula: str = "") -> None:
        self._values[key] = D(value)
        if source:
            self._sources[key] = source
        if formula:
            self._formulas[key] = formula

    def get(self, key: str) -> Decimal:
        return self._values.get(key, D(0))

    def get_source(self, key: str) -> str:
        return self._sources.get(key, "")

    def get_formula(self, key: str) -> str:
        return self._formulas.get(key, "")

    def to_dict(self) -> dict:
        return {k: dto_float(v) for k, v in self._values.items()}

    def provenance_report(self) -> str:
        lines = ["Provenance Report:"]
        for key in self._values:
            source = self._sources.get(key, "unknown")
            formula = self._formulas.get(key, "")
            lines.append(f"  {key} = {dfmt(self._values[key])} [{source}]")
            if formula:
                lines.append(f"    formula: {formula}")
        return "\n".join(lines)
