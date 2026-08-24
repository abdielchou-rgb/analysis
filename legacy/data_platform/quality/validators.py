"""quality/validators.py — 三层数据校验体系

FP2要求数据零错误。这是保障体系。

层1: 格式校验 — 类型/单位/时间戳合法性
层2: 范围校验 — 数值在合理区间
层3: 交叉验证 — 多源冲突时的裁决规则

用法:
    from legacy.data_platform.quality.validators import QualityGateway
    qg = QualityGateway()
    points = [DataPoint(name="pe", value=30.5, unit="x", source="eastmoney")]
    result = qg.validate(points)
    if result.passed:
        use_data(points)
    else:
        log_issues(result.issues)
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("v57.data.quality")

try:
    from core.models import DataPoint
except ImportError:
    from dataclasses import dataclass as _dc

    @_dc
    class DataPoint:
        name: str = ""
        value: Any = None
        unit: str = ""
        source: str = ""
        source_level: str = ""
        confidence: str = "medium"
        is_estimate: bool = False
        fiscal_year: int | None = None
        note: str = ""


@dataclass
class ValidationIssue:
    """单条校验问题"""

    validator: str = ""
    severity: str = "error"  # error / warning / info
    data_point_name: str = ""
    message: str = ""
    suggestion: str = ""


@dataclass
class ValidationResult:
    """校验结果"""

    passed: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)
    data_points: list[DataPoint] = field(default_factory=list)
    max_severity: str = "ok"  # ok / warning / error


# ── 层1: 格式校验 ──────────────────────────────────


class FormatValidator:
    """格式校验器：类型/单位/时间戳/缺失值"""

    VALID_UNITS = {
        "元",
        "美元",
        "港元",
        "亿元",
        "亿美元",
        "万",
        "%",
        "x",
        "倍",
        "家",
        "GW",
        "MW",
        "GWh",
        "万千升",
        "元/kg",
        "元/片",
        "元/W",
        "元/瓶",
        "万元/吨",
        "万辆",
        "亿",
        "点",
        "",
    }

    NUMERIC_TYPES = {int, float}

    def validate(self, points: list[DataPoint]) -> ValidationResult:
        result = ValidationResult(data_points=points)

        for dp in points:
            name = dp.name or "unknown"

            # 1. 缺失值检查
            if dp.value is None:
                result.issues.append(
                    ValidationIssue(
                        validator="format",
                        severity="error",
                        data_point_name=name,
                        message=f"值为空: {name}",
                    )
                )
                result.passed = False
                continue

            # 2. 数值类型检查
            if isinstance(dp.value, str):
                # 尝试转换
                try:
                    dp.value = float(dp.value.replace(",", ""))
                except (ValueError, AttributeError):
                    result.issues.append(
                        ValidationIssue(
                            validator="format",
                            severity="error",
                            data_point_name=name,
                            message=f"数值类型异常(字符串不可转换): {name}={dp.value}",
                        )
                    )
                    result.passed = False

            # 3. 单位一致性
            if dp.unit and dp.unit not in self.VALID_UNITS:
                result.issues.append(
                    ValidationIssue(
                        validator="format",
                        severity="warning",
                        data_point_name=name,
                        message=f"非常用单位: {name} unit={dp.unit}",
                        suggestion=f"建议使用: {self.VALID_UNITS}",
                    )
                )
                result.max_severity = "warning"

        return result


# ── 层2: 范围校验 ──────────────────────────────────


class RangeValidator:
    """范围校验器：合理值域"""

    RANGE_RULES = {
        "pe": {"min": -200, "max": 200, "unit": ["x", "倍"]},
        "pe_ttm": {"min": -200, "max": 200, "unit": ["x", "倍"]},
        "pb": {"min": 0, "max": 100, "unit": ["x", "倍"]},
        "roe": {"min": -100, "max": 100, "unit": ["%"]},
        "gross_margin": {"min": -50, "max": 100, "unit": ["%"]},
        "net_margin": {"min": -100, "max": 100, "unit": ["%"]},
        "revenue_growth": {"min": -100, "max": 500, "unit": ["%"]},
        "net_profit_growth": {"min": -500, "max": 1000, "unit": ["%"]},
        "market_cap": {"min": 0, "max": 100000, "unit": ["亿", "亿元"]},
        "debt_ratio": {"min": 0, "max": 100, "unit": ["%"]},
        "current_ratio": {"min": 0, "max": 50, "unit": ["x"]},
        "dividend_yield": {"min": 0, "max": 20, "unit": ["%"]},
    }

    def validate(self, points: list[DataPoint]) -> ValidationResult:
        result = ValidationResult(data_points=points)

        for dp in points:
            name = dp.name or ""
            value = dp.value

            # 查找匹配的规则
            rule = None
            for key, r in self.RANGE_RULES.items():
                if key in name:
                    rule = r
                    break

            if rule is None:
                continue

            try:
                val = float(value)
                if val < rule["min"] or val > rule["max"]:
                    result.issues.append(
                        ValidationIssue(
                            validator="range",
                            severity="error",
                            data_point_name=name,
                            message=f"超出合理范围 [{rule['min']}, {rule['max']}]: {name}={val}",
                        )
                    )
                    result.passed = False
            except (TypeError, ValueError):
                pass

        return result


# ── 层3: 交叉验证 ──────────────────────────────────


class CrossValidator:
    """交叉验证器：多源冲突裁决"""

    CONFLICT_THRESHOLD_PCT = 20.0  # 超过此比例标记为冲突

    def validate(self, points: list[DataPoint]) -> ValidationResult:
        result = ValidationResult(data_points=points)

        # 按名称分组
        groups: dict[str, list[DataPoint]] = {}
        for dp in points:
            name = dp.name or ""
            if name not in groups:
                groups[name] = []
            groups[name].append(dp)

        # 对每个有多源的数据点做交叉验证
        for name, group in groups.items():
            if len(group) < 2:
                continue

            values = []
            for dp in group:
                try:
                    values.append((float(dp.value), dp.source, dp.confidence))
                except (TypeError, ValueError):
                    continue

            if len(values) < 2:
                continue

            # 计算最大差异
            vals = [v[0] for v in values]
            if max(vals) == 0:
                continue
            max_diff = abs(max(vals) - min(vals)) / max(abs(v) for v in vals) * 100

            if max_diff > self.CONFLICT_THRESHOLD_PCT:
                sources_str = ", ".join(f"{v[1]}({v[0]})" for v in values)
                result.issues.append(
                    ValidationIssue(
                        validator="cross_validate",
                        severity="warning",
                        data_point_name=name,
                        message=f"多源冲突(差异{max_diff:.1f}%): {sources_str}",
                        suggestion="取中位数+标记数据分歧",
                    )
                )
                result.max_severity = "warning"
                # 标记冲突（QC flag）
                for dp in group:
                    dp.note = (dp.note or "") + f"[QC:多源冲突{max_diff:.0f}%]"

        return result


# ── 总网关 ─────────────────────────────────────────


class QualityGateway:
    """数据质量总网关 — 三层校验一次通过"""

    def __init__(self):
        self.format_validator = FormatValidator()
        self.range_validator = RangeValidator()
        self.cross_validator = CrossValidator()

    def validate(self, points: list[DataPoint], source: str = "") -> ValidationResult:
        """三层校验：格式→范围→交叉验证

        Args:
            points: DataPoint列表
            source: 数据源名称（日志用）

        Returns:
            ValidationResult: passed=False时数据不可用
        """
        if not points:
            return ValidationResult(
                passed=False, issues=[ValidationIssue(validator="gateway", severity="error", message="无数据")]
            )

        result = ValidationResult(data_points=list(points))

        # 层1: 格式
        r1 = self.format_validator.validate(points)
        result.issues.extend(r1.issues)
        if not r1.passed:
            result.passed = False

        # 层2: 范围
        r2 = self.range_validator.validate(points)
        result.issues.extend(r2.issues)
        if not r2.passed:
            result.passed = False

        # 层3: 交叉验证（仅warning，不阻断）
        r3 = self.cross_validator.validate(points)
        result.issues.extend(r3.issues)
        if r3.max_severity == "warning":
            result.max_severity = "warning"

        # 更新数据点
        result.data_points = r1.data_points

        severity = "error" if not result.passed else result.max_severity
        logger.info("QualityGateway[%s]: %d points, %d issues", severity, len(points), len(result.issues))

        return result

    def validate_and_filter(self, points: list[DataPoint], source: str = "") -> list[DataPoint]:
        """校验并过滤：只返回通过的"""
        result = self.validate(points, source)
        if result.passed:
            return result.data_points
        # 只返回没有error级问题的数据
        error_names = {i.data_point_name for i in result.issues if i.severity == "error"}
        return [dp for dp in points if dp.name not in error_names]


quality_gateway = QualityGateway()
