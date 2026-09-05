"""
IronGate 2.0 — 三层校验实现。

L1 (Hard Stop): 会计恒等式、结构性约束
L2 (Economic Physics): 商业逻辑边界、参数修正
L3 (Text-Numeric Contract): 叙述与数值一致性
"""

from __future__ import annotations

import re
from typing import Any

from engine.irongate_v2.registry import GateSeverity, GateVerdict


class L1HardStop:
    """L1: 会计恒等式与结构性硬约束。失败 → BLOCK。"""

    def validate(self, a: dict[str, Any]) -> list[GateVerdict]:
        results: list[GateVerdict] = []
        results.append(self._check_wacc_gt_growth(a))
        results.append(self._check_terminal_growth_cap(a))
        results.append(self._check_positive_revenue(a))
        results.append(self._check_positive_shares(a))
        results.append(self._check_wacc_range(a))
        results.append(self._check_tax_rate_range(a))
        return results

    def _check_wacc_gt_growth(self, a: dict) -> GateVerdict:
        wacc = a.get("wacc", 0.09)
        g = a.get("terminal_growth_rate", a.get("terminal_growth", 0.025))
        if wacc <= g:
            return GateVerdict(
                gate_id="L1-01",
                layer="L1",
                passed=False,
                severity=GateSeverity.BLOCK,
                message=f"WACC ({wacc:.1%}) ≤ 终值增长率 ({g:.1%})，违反经济学基本约束",
            )
        return GateVerdict(gate_id="L1-01", layer="L1", passed=True, severity=GateSeverity.BLOCK, message="WACC > g ✓")

    def _check_terminal_growth_cap(self, a: dict) -> GateVerdict:
        g = a.get("terminal_growth_rate", a.get("terminal_growth", 0.025))
        if g >= 0.06:
            return GateVerdict(
                gate_id="L1-02",
                layer="L1",
                passed=False,
                severity=GateSeverity.BLOCK,
                message=f"终值增长率 ({g:.1%}) ≥ 6%，超出合理经济增速上限",
            )
        return GateVerdict(
            gate_id="L1-02", layer="L1", passed=True, severity=GateSeverity.BLOCK, message="终端增长率合理 ✓"
        )

    def _check_positive_revenue(self, a: dict) -> GateVerdict:
        rev = a.get("base_revenue", 0)
        if rev <= 0:
            return GateVerdict(
                gate_id="L1-03",
                layer="L1",
                passed=False,
                severity=GateSeverity.BLOCK,
                message=f"基期营收 ({rev}) ≤ 0，无法进行估值",
            )
        return GateVerdict(gate_id="L1-03", layer="L1", passed=True, severity=GateSeverity.BLOCK, message="正营收 ✓")

    def _check_positive_shares(self, a: dict) -> GateVerdict:
        shares = a.get("shares_outstanding", a.get("total_shares", 0))
        if shares <= 0:
            return GateVerdict(
                gate_id="L1-04",
                layer="L1",
                passed=False,
                severity=GateSeverity.BLOCK,
                message=f"股本 ({shares}) ≤ 0",
            )
        return GateVerdict(gate_id="L1-04", layer="L1", passed=True, severity=GateSeverity.BLOCK, message="正股本 ✓")

    def _check_wacc_range(self, a: dict) -> GateVerdict:
        wacc = a.get("wacc", 0.09)
        if wacc < 0.02 or wacc > 0.30:
            return GateVerdict(
                gate_id="L1-05",
                layer="L1",
                passed=False,
                severity=GateSeverity.BLOCK,
                message=f"WACC ({wacc:.1%}) 超出合理范围 [2%, 30%]",
            )
        return GateVerdict(
            gate_id="L1-05", layer="L1", passed=True, severity=GateSeverity.BLOCK, message="WACC 范围合理 ✓"
        )

    def _check_tax_rate_range(self, a: dict) -> GateVerdict:
        tax = a.get("tax_rate", 0.25)
        if tax < 0.0 or tax > 0.50:
            return GateVerdict(
                gate_id="L1-06",
                layer="L1",
                passed=False,
                severity=GateSeverity.BLOCK,
                message=f"税率 ({tax:.1%}) 超出合理范围 [0%, 50%]",
            )
        return GateVerdict(
            gate_id="L1-06", layer="L1", passed=True, severity=GateSeverity.BLOCK, message="税率范围合理 ✓"
        )


class L2EconomicPhysics:
    """L2: 商业逻辑边界。失败 → 修正参数（PRUNE）。"""

    def validate(self, a: dict[str, Any]) -> list[GateVerdict]:
        results: list[GateVerdict] = []
        results.append(self._check_margin_sanity(a))
        results.append(self._check_growth_sanity(a))
        results.append(self._check_capex_vs_da(a))
        results.append(self._check_debt_ratio(a))
        return results

    def _check_margin_sanity(self, a: dict) -> GateVerdict:
        margins = a.get("ebit_margins", [])
        if margins:
            max_margin = max(margins)
            if max_margin > 0.60:
                return GateVerdict(
                    gate_id="L2-01",
                    layer="L2",
                    passed=False,
                    severity=GateSeverity.PRUNE,
                    message=f"最高利润率 ({max_margin:.1%}) > 60%，超出行业合理上限",
                    param_key="ebit_margins",
                    suggested_default=0.50,
                )
        return GateVerdict(
            gate_id="L2-01", layer="L2", passed=True, severity=GateSeverity.PRUNE, message="利润率合理 ✓"
        )

    def _check_growth_sanity(self, a: dict) -> GateVerdict:
        rates = a.get("revenue_growth_rates", [])
        if rates:
            max_growth = max(rates)
            if max_growth > 0.50:
                return GateVerdict(
                    gate_id="L2-02",
                    layer="L2",
                    passed=False,
                    severity=GateSeverity.PRUNE,
                    message=f"最高增速 ({max_growth:.1%}) > 50%，可能过于激进",
                    param_key="revenue_growth_rates",
                    suggested_default=0.30,
                )
        return GateVerdict(gate_id="L2-02", layer="L2", passed=True, severity=GateSeverity.PRUNE, message="增速合理 ✓")

    def _check_capex_vs_da(self, a: dict) -> GateVerdict:
        capex = a.get("capex_pct_revenue", 0.04)
        da = a.get("da_pct_revenue", 0.03)
        if capex > da * 3:
            return GateVerdict(
                gate_id="L2-03",
                layer="L2",
                passed=False,
                severity=GateSeverity.PRUNE,
                message=f"资本支出 ({capex:.1%}) 远超折旧 ({da:.1%})，需确认合理性",
                param_key="capex_pct_revenue",
                suggested_default=min(capex, da * 2),
            )
        return GateVerdict(
            gate_id="L2-03", layer="L2", passed=True, severity=GateSeverity.PRUNE, message="CapEx/D&A 比例合理 ✓"
        )

    def _check_debt_ratio(self, a: dict) -> GateVerdict:
        debt = a.get("net_debt", 0)
        equity = a.get("shares_outstanding", 1) * a.get("current_price", 100)
        if equity > 0:
            ratio = debt / equity
            if ratio > 2.0:
                return GateVerdict(
                    gate_id="L2-04",
                    layer="L2",
                    passed=False,
                    severity=GateSeverity.PRUNE,
                    message=f"净负债/权益 ({ratio:.1f}x) > 2x，高杠杆风险",
                    param_key="net_debt",
                    suggested_default=debt * 0.5,
                )
        return GateVerdict(
            gate_id="L2-04", layer="L2", passed=True, severity=GateSeverity.PRUNE, message="杠杆率合理 ✓"
        )

    def apply_prunes(self, a: dict[str, Any], results: list[GateVerdict]) -> dict:
        """对 PRUNE 级别失败应用参数修正"""
        pruned = {}
        for v in results:
            if not v.passed and v.severity == GateSeverity.PRUNE and v.param_key:
                old_val = a.get(v.param_key)
                if v.param_key == "ebit_margins" and isinstance(old_val, list):
                    a[v.param_key] = [min(m, v.suggested_default) for m in old_val]
                elif v.param_key == "revenue_growth_rates" and isinstance(old_val, list):
                    a[v.param_key] = [min(r, v.suggested_default) for r in old_val]
                else:
                    a[v.param_key] = v.suggested_default
                pruned[v.param_key] = {"old": old_val, "new": a[v.param_key], "reason": v.message}
        return pruned


class L3TextNumeric:
    """L3: 叙述与数值一致性。失败 → REPORT（给文本层）。"""

    def validate(self, a: dict[str, Any], report_text: str) -> list[GateVerdict]:
        results: list[GateVerdict] = []
        results.append(self._check_growth_trend_consistency(a, report_text))
        results.append(self._check_price_mentioned(a, report_text))
        results.append(self._check_no_placeholder_numbers(report_text))
        return results

    def _check_growth_trend_consistency(self, a: dict, text: str) -> GateVerdict:
        rates = a.get("revenue_growth_rates", [])
        if not rates or not text:
            return GateVerdict(
                gate_id="L3-01", layer="L3", passed=True, severity=GateSeverity.REPORT, message="无数据可校验"
            )

        avg_growth = sum(rates) / len(rates)
        text_lower = text.lower()

        declining_words = ["下滑", "下降", "萎缩", "收缩", "负增长", "decline", "shrink"]
        growing_words = ["增长", "扩张", "提升", "加速", "growth", "expand"]

        if avg_growth < 0 and any(w in text_lower for w in growing_words):
            return GateVerdict(
                gate_id="L3-01",
                layer="L3",
                passed=False,
                severity=GateSeverity.REPORT,
                message=f"模型显示负增长 ({avg_growth:.1%})，但文本使用增长性描述",
                rewrite_hint="修正文本以反映负增长趋势，或复核假设",
            )
        if avg_growth > 0.15 and any(w in text_lower for w in declining_words):
            return GateVerdict(
                gate_id="L3-01",
                layer="L3",
                passed=False,
                severity=GateSeverity.REPORT,
                message=f"模型显示高增长 ({avg_growth:.1%})，但文本使用下滑描述",
                rewrite_hint="修正文本以反映增长趋势",
            )
        return GateVerdict(
            gate_id="L3-01", layer="L3", passed=True, severity=GateSeverity.REPORT, message="增长趋势一致 ✓"
        )

    def _check_price_mentioned(self, a: dict, text: str) -> GateVerdict:
        target = a.get("fair_value_per_share") or a.get("target_price")
        if target and target > 0:
            target_str = f"{target:.0f}"
            if target_str not in text and f"{target:.2f}" not in text:
                return GateVerdict(
                    gate_id="L3-02",
                    layer="L3",
                    passed=False,
                    severity=GateSeverity.REPORT,
                    message=f"报告未提及目标价 ({target:.2f})",
                    rewrite_hint="在估值章节添加目标价",
                )
        return GateVerdict(
            gate_id="L3-02", layer="L3", passed=True, severity=GateSeverity.REPORT, message="目标价已提及 ✓"
        )

    def _check_no_placeholder_numbers(self, text: str) -> GateVerdict:
        placeholders = re.findall(r"XXX|TODO|TBD|占位|待填", text)
        if placeholders:
            return GateVerdict(
                gate_id="L3-03",
                layer="L3",
                passed=False,
                severity=GateSeverity.REPORT,
                message=f"文本包含 {len(placeholders)} 个占位符",
                rewrite_hint="替换所有占位符为实际数据",
            )
        return GateVerdict(gate_id="L3-03", layer="L3", passed=True, severity=GateSeverity.REPORT, message="无占位符 ✓")
