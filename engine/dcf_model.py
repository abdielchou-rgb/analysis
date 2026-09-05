"""
确定性 DCF 推演引擎 — 纯 Python 计算，零模型幻觉。
支持 10 期 FCF 折现 + Gordon Growth 终值 + 敏感性矩阵。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from engine.irongate import GateReport, IronGateEngine
from engine.schemas import DCFAssumptions


@dataclass
class DCFResult:
    """DCF 计算结果"""

    # 逐年预测
    revenues: List[float] = field(default_factory=list)
    ebit_margins: List[float] = field(default_factory=list)
    ebits: List[float] = field(default_factory=list)
    da_amounts: List[float] = field(default_factory=list)
    capex_amounts: List[float] = field(default_factory=list)
    wc_changes: List[float] = field(default_factory=list)
    nopat: List[float] = field(default_factory=list)
    fcf: List[float] = field(default_factory=list)
    discount_factors: List[float] = field(default_factory=list)
    pv_fcf: List[float] = field(default_factory=list)

    # 汇总
    sum_pv_fcf: float = 0.0
    terminal_fcf: float = 0.0
    terminal_value: float = 0.0
    terminal_value_pv: float = 0.0
    tv_pct: float = 0.0  # 终值现值占 EV 比重

    enterprise_value: float = 0.0
    equity_value: float = 0.0
    fair_value_per_share: float = 0.0
    upside_pct: Optional[float] = None

    # WACC 拆解
    wacc_breakdown: dict = field(default_factory=dict)

    # 敏感性矩阵
    sensitivity_wacc_range: List[float] = field(default_factory=list)
    sensitivity_g_range: List[float] = field(default_factory=list)
    sensitivity_matrix: List[List[float]] = field(default_factory=list)

    # 元数据
    confidence: str = "medium"
    warnings: List[str] = field(default_factory=list)
    gate_report: Optional[GateReport] = None


class DCFEngine:
    """确定性 DCF 引擎"""

    def __init__(self, assumptions: DCFAssumptions, skip_gates: bool = False) -> None:
        self.a = assumptions
        self.gate_report: Optional[GateReport] = None

        if not skip_gates:
            gate = IronGateEngine()
            self.gate_report = gate.validate_dcf(assumptions)
            if not self.gate_report.passed:
                errs = "; ".join(r.message for r in self.gate_report.errors)
                raise ValueError(f"IronGate DCF 校验失败:\n{errs}")

    def run(self) -> DCFResult:
        result = DCFResult(gate_report=self.gate_report)
        a = self.a

        # ── Stage 1: 逐年 FCF 推演 ─────────────────────────────────────
        curr_rev = a.base_revenue
        for i in range(a.forecast_years):
            # 营收
            curr_rev = curr_rev * (1 + a.revenue_growth_rates[i])
            ebit = curr_rev * a.ebit_margins[i]
            da = curr_rev * a.da_pct_revenue
            capex = curr_rev * a.capex_pct_revenue
            wc = curr_rev * a.wc_pct_revenue
            nopat_val = ebit * (1 - a.tax_rate)
            fcf_val = nopat_val + da - capex - wc
            df = 1 / ((1 + a.wacc) ** (i + 1))

            result.revenues.append(curr_rev)
            result.ebit_margins.append(a.ebit_margins[i])
            result.ebits.append(ebit)
            result.da_amounts.append(da)
            result.capex_amounts.append(capex)
            result.wc_changes.append(wc)
            result.nopat.append(nopat_val)
            result.fcf.append(fcf_val)
            result.discount_factors.append(df)
            result.pv_fcf.append(fcf_val * df)

        result.sum_pv_fcf = sum(result.pv_fcf)

        # ── Stage 2: Gordon Growth 终值 ─────────────────────────────────
        last_fcf = result.fcf[-1]
        result.terminal_fcf = last_fcf * (1 + a.terminal_growth_rate)
        result.terminal_value = result.terminal_fcf / (a.wacc - a.terminal_growth_rate)
        result.terminal_value_pv = result.terminal_value / ((1 + a.wacc) ** a.forecast_years)

        # ── Stage 3: 企业价值 → 每股 ───────────────────────────────────
        result.enterprise_value = result.sum_pv_fcf + result.terminal_value_pv
        result.equity_value = result.enterprise_value - a.net_debt
        result.fair_value_per_share = result.equity_value / a.shares_outstanding

        if a.current_price and a.current_price > 0:
            result.upside_pct = (result.fair_value_per_share / a.current_price - 1) * 100

        result.tv_pct = result.terminal_value_pv / result.enterprise_value if result.enterprise_value > 0 else 0.0

        # ── Stage 4: 置信度评估 ────────────────────────────────────────
        if result.tv_pct > 0.80:
            result.confidence = "low"
            result.warnings.append(f"终值占比 {result.tv_pct:.0%} > 80%，模型过度依赖永续假设")
        elif result.tv_pct > 0.60:
            result.confidence = "medium"
        else:
            result.confidence = "high"

        # ── Stage 5: 敏感性矩阵 ────────────────────────────────────────
        self._compute_sensitivity(result)

        return result

    def _compute_sensitivity(self, result: DCFResult) -> None:
        """WACC ±2pp × g ±1pp 敏感性矩阵"""
        a = self.a
        wacc_range = [a.wacc + dp * 0.01 for dp in range(-2, 3)]
        g_range = [a.terminal_growth_rate + dp * 0.005 for dp in range(-2, 3)]

        result.sensitivity_wacc_range = wacc_range
        result.sensitivity_g_range = g_range
        result.sensitivity_matrix = []

        for w in wacc_range:
            row = []
            for g in g_range:
                if w <= g:
                    row.append(float("nan"))
                    continue
                # 重算终值
                tv_fcf = result.fcf[-1] * (1 + g)
                tv = tv_fcf / (w - g)
                tv_pv = tv / ((1 + w) ** a.forecast_years)
                # 重算 PV of FCF
                sum_pv = sum(fcf / ((1 + w) ** (i + 1)) for i, fcf in enumerate(result.fcf))
                ev = sum_pv + tv_pv
                eq = ev - a.net_debt
                tp = eq / a.shares_outstanding
                row.append(round(tp, 2))
            result.sensitivity_matrix.append(row)

    def run_post_gates(self, result: DCFResult) -> GateReport:
        """后置校验：终值占比、估值合理性"""
        from engine.irongate import GateReport, GateResult

        report = GateReport()
        a = self.a

        # Gate 81: 终值占比
        if result.tv_pct > 0.90:
            report.results.append(
                GateResult(
                    "DCF-81",
                    "L3",
                    False,
                    f"终值现值占 EV {result.tv_pct:.0%} > 90%，模型缺乏短期确定性",
                    severity="error",
                )
            )
        elif result.tv_pct > 0.80:
            report.results.append(
                GateResult(
                    "DCF-81",
                    "L3",
                    False,
                    f"终值现值占 EV {result.tv_pct:.0%} > 80%，偏高",
                    severity="warning",
                )
            )
        else:
            report.results.append(GateResult("DCF-81", "L3", True, f"终值现值占 EV {result.tv_pct:.0%}"))

        # Gate 82: 公允价值为正
        if result.fair_value_per_share <= 0:
            report.results.append(
                GateResult(
                    "DCF-82",
                    "L3",
                    False,
                    f"公允价值 ({result.fair_value_per_share:.2f}) ≤ 0",
                    severity="error",
                )
            )
        else:
            report.results.append(GateResult("DCF-82", "L3", True, f"公允价值 {result.fair_value_per_share:.2f} 元/股"))

        # Gate 83: upside 极端检查
        if result.upside_pct is not None and abs(result.upside_pct) > 200:
            report.results.append(
                GateResult(
                    "DCF-83",
                    "L3",
                    False,
                    f"上行/下行空间 {result.upside_pct:+.0f}% 极端，需人工复核",
                    severity="warning",
                )
            )
        else:
            report.results.append(GateResult("DCF-83", "L3", True, "上行/下行空间在合理范围"))

        return report
