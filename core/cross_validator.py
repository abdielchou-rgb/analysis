"""V52 CrossValidator — external multi-source cross-validation engine.

Design:
  - Iron Gate 外环：对内环(SACGate)不覆盖的外部信源做多源比对
  - 差异 >15% 标记「待确认」(non-blocking warning)，不阻塞管线
  - 信源加权评分：L1_filing > L2_provider > L3_estimate > L4_analyst
  - 与 core/financial_types.py 集成，做口径感知匹配

Architecture:
  CrossValidator
    ├── compare_sources()   → 同指标多源比对
    ├── detect_outliers()   → 离群值检测(MAD)
    ├── reconcile_units()   → 单位调和（亿 vs 百万等）
    └── generate_report()   → 交叉验证报告
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional
from statistics import median

from core.financial_types import resolve_metric, reconcile_granularities

logger = logging.getLogger("v52.cross_validator")


class SourceLevel:
    """信源可信度权重"""
    WEIGHTS = {
        "L0_computed": 1.0,
        "L1_filing": 0.95,
        "L2_provider": 0.85,
        "L3_estimate": 0.60,
        "L4_analyst": 0.40,
        "L5_inference": 0.15,
        "L9_pending": 0.05,
    }

    @classmethod
    def weight(cls, level: str) -> float:
        return cls.WEIGHTS.get(level, 0.5)


@dataclass
class CrossCheckResult:
    """单个数据点的交叉验证结果"""
    metric_name: str
    granularity: str = ""
    values: list[float] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    source_levels: list[str] = field(default_factory=list)
    unit: str = ""
    median_value: float = 0.0
    mad: float = 0.0           # Median Absolute Deviation
    max_deviation_pct: float = 0.0
    has_outlier: bool = False
    outlier_indices: list[int] = field(default_factory=list)
    is_consistent: bool = True  # all values within 15% of median
    weighted_confidence: float = 0.0
    warning: str = ""


@dataclass
class CrossValidationReport:
    """完整交叉验证报告"""
    asset: str = ""
    total_metrics: int = 0
    consistent_metrics: int = 0
    flagged_metrics: int = 0      # >15% discrepancy
    severe_flagged: int = 0       # >30% discrepancy
    results: list[CrossCheckResult] = field(default_factory=list)
    granularity_warnings: list[str] = field(default_factory=list)
    overall_confidence: float = 0.0
    passed: bool = True            # Iron Gate blocking decision
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)


class CrossValidator:
    """外部交叉验证引擎 — Iron Gate 外环"""

    DISCREPANCY_WARN = 0.15    # >15% → warning
    DISCREPANCY_SEVERE = 0.30  # >30% → severe warning
    DISCREPANCY_BLOCK = 0.50   # >50% → consider blocking (not auto)

    def __init__(self):
        self.warn_threshold = self.DISCREPANCY_WARN
        self.severe_threshold = self.DISCREPANCY_SEVERE

    def validate(
        self, data_points: list, asset: str = "", text: str = ""
    ) -> CrossValidationReport:
        """执行外部交叉验证。

        Args:
            data_points: DataPoint 对象列表（多源）
            asset: 标的名称
            text: 报告正文（可选，用于提取文内引用的数字）

        Returns:
            CrossValidationReport
        """
        if not data_points:
            return CrossValidationReport(
                asset=asset, passed=True,
                recommendations=["数据为空，跳过交叉验证"],
            )

        # Step 1: 按指标名分组
        from collections import defaultdict
        by_metric: dict[str, list] = defaultdict(list)
        for dp in data_points:
            if not hasattr(dp, "name") or not hasattr(dp, "value"):
                continue
            if dp.value is None:
                continue
            metric = resolve_metric(dp.name)
            key = metric.id if metric else dp.name
            by_metric[key].append(dp)

        # Step 2: 对每个指标做同指标多源比对
        results: list[CrossCheckResult] = []
        for metric_name, dps in by_metric.items():
            if len(dps) < 2:
                continue  # 单源无法交叉验证
            r = self._compare_single_metric(metric_name, dps)
            if r is not None:
                results.append(r)

        # Step 3: 口径冲突检测
        gran_warnings = []
        try:
            gran_result = reconcile_granularities(data_points)
            gran_warnings = gran_result.get("warnings", [])
        except Exception:
            pass

        # Step 4: 汇总
        consistent = [r for r in results if r.is_consistent]
        flagged = [r for r in results if r.has_outlier]
        severe = [r for r in results if r.max_deviation_pct >= self.severe_threshold]

        # Step 5: 生成建议
        recommendations = []
        if flagged:
            recommendations.append(
                f"建议复审 {len(flagged)} 个指标的多源差异："
                + "、".join(r.metric_name for r in flagged[:5])
            )
        if gran_warnings:
            recommendations.extend(gran_warnings)
        if len(dps_by_num_sources := [r for r in results if len(r.sources) < 2]):
            recommendations.append(
                f"建议对以下指标增加冗余信源："
                + "、".join(r.metric_name for r in dps_by_num_sources[:3])
            )

        # Overall confidence: average of all weighted_confidences
        overall_conf = (
            sum(r.weighted_confidence for r in results) / len(results)
            if results else 1.0
        )

        # Non-blocking: 交叉验证不阻塞管线，差异 >50% 才建议阻塞
        passed = True
        summary = f"交叉验证完成：{len(consistent)}/{len(results)} 指标一致"
        if severe:
            summary += f"，{len(severe)} 个严重偏差(>{self.severe_threshold:.0%})"
        if flagged:
            summary += f"，{len(flagged)} 个需手动复核"

        if any(r.max_deviation_pct >= self.DISCREPANCY_BLOCK for r in results):
            passed = False
            summary += "——建议阻塞"

        return CrossValidationReport(
            asset=asset,
            total_metrics=len(results),
            consistent_metrics=len(consistent),
            flagged_metrics=len(flagged),
            severe_flagged=len(severe),
            results=results,
            granularity_warnings=gran_warnings,
            overall_confidence=overall_conf,
            passed=passed,
            summary=summary,
            recommendations=recommendations,
        )

    def _compare_single_metric(
        self, metric_name: str, dps: list
    ) -> Optional[CrossCheckResult]:
        """对单个指标的多源数据点做比对。"""
        values = []
        sources = []
        source_levels = []
        for dp in dps:
            try:
                v = float(dp.value)
            except (TypeError, ValueError):
                continue
            values.append(v)
            sources.append(getattr(dp, "source", "unknown"))
            source_levels.append(getattr(dp, "source_level", "L5_inference"))

        if len(values) < 2:
            return None

        unit = getattr(dps[0], "unit", "") if dps else ""

        # 单位调和：检测百万/亿/元不一致
        values = self._reconcile_units(values, dps)

        med = median(values)
        deviations = [abs(v - med) for v in values]
        mad = median(deviations) if len(deviations) > 1 else 0.0

        # 计算最大偏差百分比（相对于中位数）
        max_dev = max(deviations) if deviations else 0.0
        max_dev_pct = round(max_dev / abs(med) * 100, 1) if med != 0 else 0.0

        # 离群值检测：偏差 > 3*MAD 或 >15%
        outlier_indices = []
        for i, dev in enumerate(deviations):
            if mad > 0 and dev > 3 * mad:
                outlier_indices.append(i)
            elif med != 0 and abs(values[i] - med) / abs(med) > self.warn_threshold:
                outlier_indices.append(i)

        has_outlier = len(outlier_indices) > 0
        is_consistent = not has_outlier and max_dev_pct < self.warn_threshold * 100

        # 加权信度
        weights = [SourceLevel.weight(lv) for lv in source_levels]
        weighted_conf = (
            sum(w * (1 - min(abs(v - med) / max(abs(med), 1), 1))
                for v, w in zip(values, weights))
            / max(sum(weights), 1)
        )

        metric = resolve_metric(metric_name)
        gran = metric.granularity.value if metric else ""

        warning = ""
        if has_outlier:
            outlier_details = []
            for idx in outlier_indices:
                outlier_details.append(
                    f"{sources[idx]}({values[idx]:.2f}{unit}, 偏差{deviations[idx]/max(abs(med),1)*100:.1f}%)"
                )
            warning = f"数据差异: {', '.join(outlier_details)}"
            if max_dev_pct >= self.DISCREPANCY_SEVERE * 100:
                warning += f" [严重]"
            if max_dev_pct >= self.DISCREPANCY_BLOCK * 100:
                warning += f" [建议阻塞]"

        return CrossCheckResult(
            metric_name=metric_name,
            granularity=gran,
            values=values,
            sources=sources,
            source_levels=source_levels,
            unit=unit,
            median_value=round(med, 4),
            mad=round(mad, 4),
            max_deviation_pct=max_dev_pct,
            has_outlier=has_outlier,
            outlier_indices=outlier_indices,
            is_consistent=is_consistent,
            weighted_confidence=round(weighted_conf, 3),
            warning=warning,
        )

    def _reconcile_units(self, values: list[float], dps: list) -> list[float]:
        """单位调和：检测并统一单位（亿 vs 百万 vs 元）。"""
        units = [getattr(dp, "unit", "") for dp in dps]
        unique_units = set(u for u in units if u)
        if len(unique_units) <= 1:
            return values

        # 如果存在不同单位，尝试统一为"亿"
        adjusted = list(values)
        for i, (v, u) in enumerate(zip(values, units)):
            if u == "百万" or u == "百万":
                adjusted[i] = v / 100
            elif u == "元":
                adjusted[i] = v / 1e8
            elif u == "万":
                adjusted[i] = v / 10000
            elif u == "%" and any(other in ["百分点", "bps"] for other in unique_units):
                pass  # 百分比保持
        return adjusted

    # ── 三表勾稽验证 ───────────────────────────────────────────
    # 容忍度参数（可通过 __init__ 覆盖）
    RECONCILIATION_TOLERANCE = 0.05   # 5% 勾稽容差（财报级通常 <1%，估计级放宽至 5%）
    CF_RECONCILIATION_TOLERANCE = 0.10  # 经营现金流勾稽容差（非现金项目影响，放宽至 10%）

    def check_three_statement_consistency(
        self, financials: dict
    ) -> dict:
        """三表勾稽验证（PL ↔ BS ↔ CF）。

        验证三项核心勾稽关系：
          ① 净利润 = 收入 - 成本 - 费用（在容差内）
          ② 期末留存收益 = 期初 + 净利润 - 分红
          ③ 经营现金流与利润表勾稽（可接受差异容差参数化）

        Args:
            financials: {
                "revenue": float,          # 营业收入（亿）
                "cost_of_revenue": float,  # 营业成本（亿）
                "operating_expenses": float, # 费用合计（亿）
                "net_profit": float,       # 净利润（亿）
                "retained_earnings_begin": float,  # 期初留存收益
                "retained_earnings_end": float,    # 期末留存收益
                "dividends": float,        # 分红（亿）
                "operating_cf": float,     # 经营活动现金流净额（亿）
                "non_cash_items": float,   # 非现金项目（折旧+摊销+减值等，可选）
            }

        Returns:
            {
                "passed": bool,
                "checks": [
                    {"name": str, "passed": bool, "expected": float,
                     "actual": float, "diff_pct": float, "detail": str},
                    ...
                ],
                "warnings": [str],
                "overall_detail": str,
            }
        """
        checks = []
        warnings = []
        all_passed = True

        rev = financials.get("revenue")
        cost = financials.get("cost_of_revenue", 0)
        opex = financials.get("operating_expenses", 0)
        np_actual = financials.get("net_profit")
        re_begin = financials.get("retained_earnings_begin")
        re_end = financials.get("retained_earnings_end")
        dividends = financials.get("dividends", 0)
        ocf = financials.get("operating_cf")
        non_cash = financials.get("non_cash_items", 0)

        # ── ① 净利润 = 收入 - 成本 - 费用 ──
        if all(v is not None for v in [rev, np_actual]):
            np_expected = rev - cost - opex
            if np_expected != 0:
                diff_pct = abs(np_actual - np_expected) / abs(np_expected)
            else:
                diff_pct = float("inf") if np_actual != 0 else 0.0
            check_passed = diff_pct <= self.RECONCILIATION_TOLERANCE
            checks.append({
                "name": "净利润勾稽（收入-成本-费用）",
                "passed": check_passed,
                "expected": round(np_expected, 4),
                "actual": np_actual,
                "diff_pct": round(diff_pct * 100, 2),
                "detail": (
                    f"预期净利润 {np_expected:.4f} 亿 vs 实际 {np_actual:.4f} 亿"
                    f"（差异 {diff_pct*100:.2f}%）"
                ),
            })
            if not check_passed:
                all_passed = False
                warnings.append(
                    f"净利润勾稽差异 {diff_pct*100:.2f}% > {self.RECONCILIATION_TOLERANCE*100:.0f}% 容差"
                )
        else:
            warnings.append("净利润勾稽跳过：缺少收入或净利润数据")

        # ── ② 期末留存收益 = 期初 + 净利润 - 分红 ──
        if all(v is not None for v in [re_begin, re_end, np_actual]):
            re_expected = re_begin + np_actual - dividends
            if re_expected != 0:
                diff_pct = abs(re_end - re_expected) / abs(re_expected)
            else:
                diff_pct = float("inf") if re_end != 0 else 0.0
            check_passed = diff_pct <= self.RECONCILIATION_TOLERANCE
            checks.append({
                "name": "留存收益勾稽（期初+净利润-分红）",
                "passed": check_passed,
                "expected": round(re_expected, 4),
                "actual": re_end,
                "diff_pct": round(diff_pct * 100, 2),
                "detail": (
                    f"预期期末留存 {re_expected:.4f} 亿 vs 实际 {re_end:.4f} 亿"
                    f"（差异 {diff_pct*100:.2f}%）"
                ),
            })
            if not check_passed:
                all_passed = False
                warnings.append(
                    f"留存收益勾稽差异 {diff_pct*100:.2f}% > {self.RECONCILIATION_TOLERANCE*100:.0f}% 容差"
                )
        else:
            warnings.append("留存收益勾稽跳过：缺少期初/期末留存收益数据")

        # ── ③ 经营现金流与利润表勾稽 ──
        if all(v is not None for v in [ocf, np_actual]):
            # 经营现金流 ≈ 净利润 + 非现金项目 ± 营运资本变动
            # 简化版：ocf 与 np 不应差异过大（>50% 需关注）
            cf_diff = abs(ocf - np_actual)
            ref_val = max(abs(np_actual), abs(ocf), 1)
            diff_pct = cf_diff / ref_val

            # 若有 non_cash_items，做更精细的勾稽
            np_plus_nc = np_actual + non_cash
            cf_diff_adj = abs(ocf - np_plus_nc)
            diff_pct_adj = cf_diff_adj / max(abs(np_plus_nc), abs(ocf), 1) if max(abs(np_plus_nc), abs(ocf), 1) > 0 else 0

            check_passed = diff_pct <= self.CF_RECONCILIATION_TOLERANCE
            checks.append({
                "name": "经营现金流与利润表勾稽",
                "passed": check_passed,
                "expected": round(np_actual, 4),
                "actual": ocf,
                "diff_pct": round(diff_pct * 100, 2),
                "detail": (
                    f"净利润 {np_actual:.4f} 亿 vs 经营现金流 {ocf:.4f} 亿"
                    f"（差异 {diff_pct*100:.2f}%，"
                    f"含非现金项目调整后差异 {diff_pct_adj*100:.2f}%）"
                ),
            })
            if not check_passed:
                all_passed = False
                warnings.append(
                    f"经营现金流勾稽差异 {diff_pct*100:.2f}% > {self.CF_RECONCILIATION_TOLERANCE*100:.0f}% 容差"
                )
        else:
            warnings.append("经营现金流勾稽跳过：缺少经营现金流或净利润数据")

        n_passed = sum(1 for c in checks if c["passed"])
        overall_detail = f"三表勾稽：{n_passed}/{len(checks)} 项通过"
        if not all_passed:
            overall_detail += "（存在勾稽差异，建议复核）"

        return {
            "passed": all_passed,
            "checks": checks,
            "warnings": warnings,
            "overall_detail": overall_detail,
        }


# ── 便捷函数 ────────────────────────────────────────────────

def quick_validate(data_points: list, asset: str = "") -> CrossValidationReport:
    """单行交叉验证调用。"""
    cv = CrossValidator()
    return cv.validate(data_points, asset=asset)


__all__ = [
    "CrossValidator", "CrossValidationReport", "CrossCheckResult",
    "SourceLevel", "quick_validate",
]
