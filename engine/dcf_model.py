"""
确定性 DCF 推演引擎 — 纯 Python 计算，零模型幻觉。
支持 10 期 FCF 折现 + Gordon Growth 终值 + 敏感性矩阵。

Phase 1: 全链路 Decimal 精度 + Provenance 追溯。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from engine.irongate import GateReport, IronGateEngine
from engine.precision import D, PreciseValuation, dto_float


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
    tv_pct: float = 0.0

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
    """确定性 DCF 引擎 — Decimal 精度"""

    def __init__(self, assumptions, skip_gates: bool = False) -> None:
        self.a = assumptions
        self.gate_report: Optional[GateReport] = None
        self.provenance = PreciseValuation()

        # 计算动态 WACC
        if assumptions.use_dynamic_wacc:
            self._wacc = assumptions.compute_dynamic_wacc()
        else:
            self._wacc = assumptions.wacc

        if not skip_gates:
            gate = IronGateEngine()
            self.gate_report = gate.validate_dcf(assumptions)
            if not self.gate_report.passed:
                errs = "; ".join(r.message for r in self.gate_report.errors)
                raise ValueError(f"IronGate DCF 校验失败:\n{errs}")

    def run(self) -> DCFResult:
        result = DCFResult(gate_report=self.gate_report)
        a = self.a
        wacc = D(self._wacc)
        tax = D(a.tax_rate)
        terminal_g = D(a.terminal_growth_rate)
        shares = D(a.shares_outstanding)
        net_debt = D(a.net_debt)

        # ── Stage 1: 逐年 FCF 推演 (Decimal) ────────────────────────────
        curr_rev = D(a.base_revenue)
        self.provenance.set("base_revenue", a.base_revenue, source="user_input")

        for i in range(a.forecast_years):
            g = D(a.revenue_growth_rates[i])
            margin = D(a.ebit_margins[i])
            da_pct = D(a.da_pct_revenue)
            capex_pct = D(a.capex_pct_revenue)
            wc_pct = D(a.wc_pct_revenue)

            curr_rev = curr_rev * (D(1) + g)
            ebit = curr_rev * margin
            da = curr_rev * da_pct
            capex = curr_rev * capex_pct
            wc = curr_rev * wc_pct
            nopat_val = ebit * (D(1) - tax)
            fcf_val = nopat_val + da - capex - wc
            df = D(1) / ((D(1) + wacc) ** (i + 1))

            # 记录溯源
            self.provenance.set(
                f"year{i + 1}.revenue",
                curr_rev,
                source="computed",
                formula=f"prev_rev × (1 + g[{i}])",
            )
            self.provenance.set(
                f"year{i + 1}.fcf",
                fcf_val,
                source="computed",
                formula="NOPAT + D&A - CapEx - ΔWC",
            )

            result.revenues.append(dto_float(curr_rev))
            result.ebit_margins.append(a.ebit_margins[i])
            result.ebits.append(dto_float(ebit))
            result.da_amounts.append(dto_float(da))
            result.capex_amounts.append(dto_float(capex))
            result.wc_changes.append(dto_float(wc))
            result.nopat.append(dto_float(nopat_val))
            result.fcf.append(dto_float(fcf_val))
            result.discount_factors.append(dto_float(df))
            result.pv_fcf.append(dto_float(fcf_val * df))

        result.sum_pv_fcf = sum(result.pv_fcf)

        # ── Stage 2: Gordon Growth 终值 (Decimal) ────────────────────────
        last_fcf = D(result.fcf[-1])
        result.terminal_fcf = dto_float(last_fcf * (D(1) + terminal_g))
        result.terminal_value = dto_float(last_fcf * (D(1) + terminal_g) / (wacc - terminal_g))
        result.terminal_value_pv = dto_float(D(result.terminal_value) / ((D(1) + wacc) ** a.forecast_years))

        self.provenance.set("terminal_fcf", result.terminal_fcf, formula="last_fcf × (1+g)")
        self.provenance.set(
            "terminal_value",
            result.terminal_value,
            formula="terminal_fcf / (WACC - g)",
        )

        # ── Stage 3: 企业价值 → 每股 (Decimal) ──────────────────────────
        ev = D(result.sum_pv_fcf) + D(result.terminal_value_pv)
        eq = ev - net_debt
        result.enterprise_value = dto_float(ev)
        result.equity_value = dto_float(eq)
        result.fair_value_per_share = dto_float(eq / shares)

        self.provenance.set("enterprise_value", result.enterprise_value, formula="ΣPV(FCF) + PV(TV)")
        self.provenance.set("equity_value", result.equity_value, formula="EV - Net Debt")
        self.provenance.set("fair_value", result.fair_value_per_share, formula="Equity / Shares")

        if a.current_price and a.current_price > 0:
            result.upside_pct = (result.fair_value_per_share / a.current_price - 1) * 100

        result.tv_pct = result.terminal_value_pv / result.enterprise_value if result.enterprise_value > 0 else 0.0

        # ── Stage 4: 置信度评估 ─────────────────────────────────────────
        if result.tv_pct > 0.80:
            result.confidence = "low"
            result.warnings.append(f"终值占比 {result.tv_pct:.0%} > 80%，模型过度依赖永续假设")
        elif result.tv_pct > 0.60:
            result.confidence = "medium"
        else:
            result.confidence = "high"

        # ── Stage 5: 敏感性矩阵 (Decimal) ──────────────────────────────
        self._compute_sensitivity(result)

        result.wacc_breakdown = {
            "wacc_used": dto_float(wacc),
            "is_dynamic": a.use_dynamic_wacc,
            "industry_beta": a.industry_beta,
            "target_debt_ratio": a.target_debt_ratio,
        }

        return result

    def _compute_sensitivity(self, result: DCFResult) -> None:
        """WACC ±2pp × g ±1pp 敏感性矩阵 (Decimal)"""
        a = self.a
        wacc = D(self._wacc)
        terminal_g = D(a.terminal_growth_rate)
        shares = D(a.shares_outstanding)
        net_debt = D(a.net_debt)

        wacc_range = [wacc + D(dp) * D("0.01") for dp in range(-2, 3)]
        g_range = [terminal_g + D(dp) * D("0.005") for dp in range(-2, 3)]

        result.sensitivity_wacc_range = [dto_float(w) for w in wacc_range]
        result.sensitivity_g_range = [dto_float(g) for g in g_range]
        result.sensitivity_matrix = []

        fcf_dec = [D(f) for f in result.fcf]
        n_years = a.forecast_years

        for w in wacc_range:
            row = []
            for g in g_range:
                if w <= g:
                    row.append(float("nan"))
                    continue
                tv_fcf = fcf_dec[-1] * (D(1) + g)
                tv = tv_fcf / (w - g)
                tv_pv = tv / ((D(1) + w) ** n_years)
                sum_pv = sum(f / ((D(1) + w) ** (i + 1)) for i, f in enumerate(fcf_dec))
                ev = sum_pv + tv_pv
                eq = ev - net_debt
                tp = eq / shares
                row.append(round(dto_float(tp), 2))
            result.sensitivity_matrix.append(row)

    def run_post_gates(self, result: DCFResult) -> GateReport:
        """后置校验：终值占比、估值合理性"""
        from engine.irongate import GateResult

        report = GateReport()

        if result.tv_pct > 0.90:
            report.results.append(
                GateResult("DCF-81", "L3", False, f"终值现值占 EV {result.tv_pct:.0%} > 90%", severity="error")
            )
        elif result.tv_pct > 0.80:
            report.results.append(
                GateResult("DCF-81", "L3", False, f"终值现值占 EV {result.tv_pct:.0%} > 80%", severity="warning")
            )
        else:
            report.results.append(GateResult("DCF-81", "L3", True, f"终值现值占 EV {result.tv_pct:.0%}"))

        if result.fair_value_per_share <= 0:
            report.results.append(
                GateResult("DCF-82", "L3", False, f"公允价值 ({result.fair_value_per_share:.2f}) ≤ 0", severity="error")
            )
        else:
            report.results.append(GateResult("DCF-82", "L3", True, f"公允价值 {result.fair_value_per_share:.2f} 元/股"))

        if result.upside_pct is not None and abs(result.upside_pct) > 200:
            report.results.append(
                GateResult("DCF-83", "L3", False, f"上行/下行 {result.upside_pct:+.0f}% 极端", severity="warning")
            )
        else:
            report.results.append(GateResult("DCF-83", "L3", True, "上行/下行空间在合理范围"))

        return report
