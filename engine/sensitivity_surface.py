"""
多维敏感性分析 — Sensitivity Surface。
扩展 DCF 的 2D 敏感性矩阵到 N 维。

支持:
1. 2D: WACC × g → 目标价
2. 3D: WACC × g × margin → 目标价
3. Tornado: 各参数对目标价的独立影响
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from engine.precision import D, dto_float


@dataclass
class SensitivityResult:
    """敏感性分析结果"""

    param_names: list[str] = field(default_factory=list)
    param_ranges: dict[str, list[float]] = field(default_factory=dict)
    matrix: list[list[float]] = field(default_factory=list)
    base_value: float = 0.0
    tornado: list[dict] = field(default_factory=list)


class SensitivitySurface:
    """多维敏感性分析引擎"""

    def __init__(
        self,
        compute_fn: Callable[[dict], float],
        base_assumptions: dict[str, Any],
    ):
        self.compute_fn = compute_fn
        self.base = base_assumptions.copy()

    def compute_2d(
        self,
        param_x: str,
        param_y: str,
        range_x: list[float] | None = None,
        range_y: list[float] | None = None,
        steps: int = 5,
    ) -> SensitivityResult:
        """2D 敏感性: param_x × param_y → 目标指标"""
        base_x = D(self.base.get(param_x, 0))
        base_y = D(self.base.get(param_y, 0))

        if range_x is None:
            range_x = [dto_float(base_x * D(1 + dp * 0.05)) for dp in range(-steps // 2, steps // 2 + 1)]
        if range_y is None:
            range_y = [dto_float(base_y * D(1 + dp * 0.05)) for dp in range(-steps // 2, steps // 2 + 1)]

        matrix = []
        for x in range_x:
            row = []
            for y in range_y:
                modified = {**self.base, param_x: x, param_y: y}
                try:
                    val = self.compute_fn(modified)
                    row.append(round(val, 2))
                except Exception:
                    row.append(float("nan"))
            matrix.append(row)

        base_val = self.compute_fn(self.base)

        return SensitivityResult(
            param_names=[param_x, param_y],
            param_ranges={param_x: range_x, param_y: range_y},
            matrix=matrix,
            base_value=round(base_val, 2),
        )

    def tornado(
        self,
        param_ranges: dict[str, tuple[float, float]],
    ) -> SensitivityResult:
        """Tornado 图: 各参数对目标价的独立影响"""
        base_val = D(self.compute_fn(self.base))
        bars = []

        for param, (low, high) in param_ranges.items():
            # Low scenario
            modified_low = {**self.base, param: low}
            val_low = D(self.compute_fn(modified_low))

            # High scenario
            modified_high = {**self.base, param: high}
            val_high = D(self.compute_fn(modified_high))

            swing = abs(val_high - val_low)
            bars.append(
                {
                    "param": param,
                    "low_value": dto_float(val_low),
                    "high_value": dto_float(val_high),
                    "swing": dto_float(swing),
                    "low_input": low,
                    "high_input": high,
                }
            )

        # 按 swing 排序
        bars.sort(key=lambda b: b["swing"], reverse=True)

        return SensitivityResult(
            param_names=[b["param"] for b in bars],
            base_value=dto_float(base_val),
            tornado=bars,
        )
