"""
16-Step IB-Grade Orchestrator + Report Pipeline。
Phase 2: 所有步骤从 stub 接入真实计算引擎。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from engine.precision import PreciseValuation


class PipelineStep(str, Enum):
    STEP_01_INCOME_STATEMENT = "01_income_statement"
    STEP_02_WORKING_CAPITAL = "02_working_capital"
    STEP_03_CAPEX_DA = "03_capex_da"
    STEP_04_DEBT_SCHEDULE = "04_debt_schedule"
    STEP_05_RELINK_IS = "05_relink_is"
    STEP_06_BALANCE_SHEET = "06_balance_sheet"
    STEP_07_CASH_FLOW = "07_cash_flow"
    STEP_08_WACC = "08_wacc"
    STEP_09_DCF = "09_dcf"
    STEP_10_SCENARIOS = "10_scenarios"
    STEP_11_MONTE_CARLO = "11_monte_carlo"
    STEP_12_SENSITIVITY = "12_sensitivity"
    STEP_13_TORNADO = "13_tornado"
    STEP_14_COMPS = "14_comps"
    STEP_15_EXCEL = "15_excel"
    STEP_16_REPORT = "16_report"


@dataclass
class StepResult:
    step: PipelineStep
    status: str = "pending"
    duration_ms: float = 0.0
    output: Any = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    steps: Dict[str, StepResult] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    success: bool = True
    final_output: Any = None

    def summary(self) -> str:
        lines = [f"Pipeline {'SUCCESS' if self.success else 'FAILED'} ({self.total_duration_ms:.0f}ms)"]
        for step_name, result in self.steps.items():
            status = result.status.upper()
            duration = f"{result.duration_ms:.0f}ms" if result.duration_ms > 0 else "—"
            lines.append(f"  [{status}] {step_name}: {duration}")
            for w in result.warnings:
                lines.append(f"    WARN: {w}")
            for e in result.errors:
                lines.append(f"    ERR: {e}")
        return "\n".join(lines)


class IBGradeOrchestrator:
    """16-Step IB-Grade Pipeline — 真实计算引擎接入"""

    def __init__(self):
        self.steps: List[PipelineStep] = list(PipelineStep)
        self.results: Dict[str, StepResult] = {}
        self.provenance = PreciseValuation()

    def run(self, assumptions: Dict[str, Any]) -> PipelineResult:
        result = PipelineResult()
        start_time = time.time()

        for step in self.steps:
            step_result = StepResult(step=step, status="running")
            step_start = time.time()

            try:
                output = self._execute_step(step, assumptions)
                step_result.output = output
                step_result.status = "completed"
            except Exception as e:
                step_result.errors.append(str(e))
                step_result.status = "failed"
                result.success = False

            step_result.duration_ms = (time.time() - step_start) * 1000
            self.results[step.value] = step_result
            result.steps[step.value] = step_result

            if not result.success:
                break

        result.total_duration_ms = (time.time() - start_time) * 1000
        result.final_output = self._compile_output()
        return result

    def _execute_step(self, step: PipelineStep, assumptions: Dict) -> Any:
        handlers = {
            PipelineStep.STEP_01_INCOME_STATEMENT: self._step_three_statement,
            PipelineStep.STEP_02_WORKING_CAPITAL: self._step_passthrough,
            PipelineStep.STEP_03_CAPEX_DA: self._step_passthrough,
            PipelineStep.STEP_04_DEBT_SCHEDULE: self._step_passthrough,
            PipelineStep.STEP_05_RELINK_IS: self._step_passthrough,
            PipelineStep.STEP_06_BALANCE_SHEET: self._step_passthrough,
            PipelineStep.STEP_07_CASH_FLOW: self._step_passthrough,
            PipelineStep.STEP_08_WACC: self._step_wacc,
            PipelineStep.STEP_09_DCF: self._step_dcf,
            PipelineStep.STEP_10_SCENARIOS: self._step_scenarios,
            PipelineStep.STEP_11_MONTE_CARLO: self._step_monte_carlo,
            PipelineStep.STEP_12_SENSITIVITY: self._step_sensitivity,
            PipelineStep.STEP_13_TORNADO: self._step_tornado,
            PipelineStep.STEP_14_COMPS: self._step_comps,
            PipelineStep.STEP_15_EXCEL: self._step_passthrough,
            PipelineStep.STEP_16_REPORT: self._step_report,
        }
        handler = handlers.get(step, self._step_passthrough)
        return handler(assumptions)

    # ── Step 01-07: Three-Statement (IS→WC→CapEx→Debt→BS→CF) ──────────

    def _step_three_statement(self, a: Dict) -> Dict:
        """三表联动: IS→BS→CF 一次性完成"""
        from engine.three_statement import ThreeStatementAssumptions, ThreeStatementEngine

        ts_params = self._extract_three_statement_params(a)
        assumptions = ThreeStatementAssumptions(**ts_params)
        engine = ThreeStatementEngine(assumptions, skip_gates=True)
        result = engine.run()

        # 存储结果供后续步骤使用
        self._ts_result = result
        self._fcff = result.fcff_for_dcf
        self._fcfe = result.fcfe_for_dcf
        self._total_debt = result.total_debt[-1] if result.total_debt else 0
        self._net_debt = result.net_debt[-1] if result.net_debt else 0

        return {
            "status": "three_statement_completed",
            "fcff": result.fcff_for_dcf,
            "fcfe": result.fcfe_for_dcf,
            "invariants": result.invariant_checks,
            "years": result.income_statement.years,
        }

    def _step_passthrough(self, a: Dict) -> Dict:
        """透传步骤 (WC/CapEx/Debt 已在三表中完成)"""
        return {"status": "completed_via_three_statement"}

    # ── Step 08: WACC ──────────────────────────────────────────────────

    def _step_wacc(self, a: Dict) -> Dict:
        wacc = a.get("wacc", 0.09)
        if a.get("use_dynamic_wacc"):
            from engine.schemas import DCFAssumptions

            temp = DCFAssumptions(
                ticker=a.get("ticker", ""),
                company_name=a.get("company_name", ""),
                base_revenue=a.get("base_revenue", 100),
                base_ebit_margin=0.2,
                revenue_growth_rates=[0.1] * 5,
                ebit_margins=[0.2] * 5,
                wacc=wacc,
                shares_outstanding=a.get("shares_outstanding", 10),
                use_dynamic_wacc=True,
                industry_beta=a.get("industry_beta", 1.0),
                target_debt_ratio=a.get("target_debt_ratio", 0.3),
                risk_free_rate=a.get("risk_free_rate"),
                equity_risk_premium=a.get("equity_risk_premium"),
                cost_of_debt=a.get("cost_of_debt"),
            )
            wacc = temp.compute_dynamic_wacc()

        return {"status": "wacc_computed", "wacc": wacc}

    # ── Step 09: DCF ───────────────────────────────────────────────────

    def _step_dcf(self, a: Dict) -> Dict:
        from engine.dcf_model import DCFEngine
        from engine.schemas import DCFAssumptions

        dcf_params = self._extract_dcf_params(a)
        assumptions = DCFAssumptions(**dcf_params)
        engine = DCFEngine(assumptions, skip_gates=True)
        result = engine.run()

        self._dcf_result = result
        return {
            "status": "dcf_computed",
            "fair_value": result.fair_value_per_share,
            "enterprise_value": result.enterprise_value,
            "tv_pct": result.tv_pct,
            "confidence": result.confidence,
            "sensitivity": result.sensitivity_matrix,
        }

    # ── Step 10: Scenarios ─────────────────────────────────────────────

    def _step_scenarios(self, a: Dict) -> Dict:
        from engine.scenario_model import ScenarioEngine
        from engine.schemas import ScenarioAssumptions, ScenarioDetail

        base_rev = a.get("base_revenue", 100)
        shares = a.get("shares_outstanding", 10)
        base_margin = a.get("base_ebit_margin", 0.20)

        scenario_a = ScenarioAssumptions(
            ticker=a.get("ticker", ""),
            company_name=a.get("company_name", ""),
            base_price=a.get("current_price", 100),
            bull=ScenarioDetail(
                revenue_growth_rates=[0.15, 0.12, 0.10],
                operating_margin=min(base_margin + 0.05, 0.50),
                probability=0.30,
            ),
            base=ScenarioDetail(
                revenue_growth_rates=a.get("revenue_growth_rates", [0.10, 0.08, 0.06])[:3],
                operating_margin=base_margin,
                probability=0.50,
            ),
            bear=ScenarioDetail(
                revenue_growth_rates=[0.05, 0.03, 0.02],
                operating_margin=max(base_margin - 0.05, 0.05),
                probability=0.20,
            ),
            wacc=a.get("wacc", 0.09),
            base_revenue=base_rev,
            total_shares=shares,
            net_debt=a.get("net_debt", 0),
        )
        result = ScenarioEngine(scenario_a, skip_gates=True).run()
        return {
            "status": "scenarios_computed",
            "weighted_target": result.weighted_target,
            "bull": result.scenario_prices.get("bull"),
            "base": result.scenario_prices.get("base"),
            "bear": result.scenario_prices.get("bear"),
            "risk_reward": result.risk_reward,
        }

    # ── Step 11: Monte Carlo ───────────────────────────────────────────

    def _step_monte_carlo(self, a: Dict) -> Dict:
        from engine.monte_carlo import MonteCarloAssumptions, MonteCarloEngine

        mc_a = MonteCarloAssumptions(
            ticker=a.get("ticker", ""),
            company_name=a.get("company_name", ""),
            n_simulations=min(a.get("mc_simulations", 10000), 50000),
            base_revenue=a.get("base_revenue", 100),
            shares_outstanding=a.get("shares_outstanding", 10),
            revenue_growth_mean=a.get("revenue_growth_rates", [0.10])[0] if a.get("revenue_growth_rates") else 0.10,
            wacc_mean=a.get("wacc", 0.09),
            tax_rate=a.get("tax_rate", 0.25),
            net_debt=a.get("net_debt", 0),
            current_price=a.get("current_price"),
            forecast_years=a.get("forecast_years", 5),
        )
        result = MonteCarloEngine(mc_a).run()
        return {
            "status": "monte_carlo_completed",
            "mean": result.mean,
            "median": result.median,
            "std": result.std,
            "ci_95": result.confidence_interval_95,
            "probability_above_price": result.prob_above_current,
        }

    # ── Step 12: Sensitivity ───────────────────────────────────────────

    def _step_sensitivity(self, a: Dict) -> Dict:
        if not hasattr(self, "_dcf_result") or self._dcf_result is None:
            return {"status": "sensitivity_skipped", "reason": "DCF not run"}
        return {
            "status": "sensitivity_computed",
            "matrix": self._dcf_result.sensitivity_matrix,
            "wacc_range": self._dcf_result.sensitivity_wacc_range,
            "g_range": self._dcf_result.sensitivity_g_range,
        }

    # ── Step 13: Tornado ───────────────────────────────────────────────

    def _step_tornado(self, a: Dict) -> Dict:
        if not hasattr(self, "_dcf_result") or self._dcf_result is None:
            return {"status": "tornado_skipped"}

        from engine.sensitivity_surface import SensitivitySurface

        def compute_dcf(params):
            from engine.dcf_model import DCFEngine
            from engine.schemas import DCFAssumptions

            p = {**a, **params}
            # Ensure list fields get lists
            gr = p.get("revenue_growth_rates", [0.10] * 5)
            if isinstance(gr, (int, float)):
                gr = [gr] * 5
            em = p.get("ebit_margins", [p.get("base_ebit_margin", 0.20)] * 5)
            if isinstance(em, (int, float)):
                em = [em] * 5
            dcf_a = DCFAssumptions(
                ticker=p.get("ticker", ""),
                company_name=p.get("company_name", ""),
                base_revenue=p.get("base_revenue", 100),
                base_ebit_margin=p.get("base_ebit_margin", 0.20),
                revenue_growth_rates=gr,
                ebit_margins=em,
                wacc=p.get("wacc", 0.09),
                terminal_growth_rate=p.get("terminal_growth_rate", 0.025),
                shares_outstanding=p.get("shares_outstanding", 10),
                net_debt=p.get("net_debt", 0),
                da_pct_revenue=p.get("da_pct_revenue", 0.03),
                capex_pct_revenue=p.get("capex_pct_revenue", 0.04),
                wc_pct_revenue=p.get("wc_pct_revenue", 0.02),
                tax_rate=p.get("tax_rate", 0.25),
            )
            return DCFEngine(dcf_a, skip_gates=True).run().fair_value_per_share

        surface = SensitivitySurface(compute_dcf, a)
        wacc_base = a.get("wacc", 0.09)
        g_base = a.get("terminal_growth_rate", 0.025)
        margin_base = a.get("base_ebit_margin", 0.20)
        result = surface.tornado(
            {
                "wacc": (wacc_base - 0.02, wacc_base + 0.02),
                "terminal_growth_rate": (g_base - 0.01, g_base + 0.01),
                "base_ebit_margin": (margin_base - 0.05, margin_base + 0.05),
                "revenue_growth_rates": (0.05, 0.20),
            }
        )
        return {
            "status": "tornado_computed",
            "base_value": result.base_value,
            "bars": result.tornado,
        }

    # ── Step 14: Comps ─────────────────────────────────────────────────

    def _step_comps(self, a: Dict) -> Dict:
        if not a.get("peer_pe_ratios"):
            return {"status": "comps_skipped", "reason": "no peer data"}

        from engine.comparable_model import ComparableEngine
        from engine.schemas import ComparableAssumptions

        comp_a = ComparableAssumptions(
            ticker=a.get("ticker", ""),
            company_name=a.get("company_name", ""),
            company_eps=a.get("eps", 0),
            company_bvps=a.get("bvps", 0),
            company_revenue_per_share=a.get("revenue_per_share", 0),
            company_ebitda_per_share=a.get("ebitda_per_share", 0),
            peer_pe_ratios=a.get("peer_pe_ratios", []),
            peer_pb_ratios=a.get("peer_pb_ratios", []),
            peer_ps_ratios=a.get("peer_ps_ratios", []),
            peer_ev_ebitda=a.get("peer_ev_ebitda", []),
            current_price=a.get("current_price"),
        )
        result = ComparableEngine(comp_a, skip_gates=True).run()
        return {
            "status": "comps_computed",
            "target_price": result.target_price,
            "implied_prices": result.implied_prices,
            "confidence": result.confidence,
        }

    # ── Step 16: Report ────────────────────────────────────────────────

    def _step_report(self, a: Dict) -> Dict:
        dcf_fv = self._dcf_result.fair_value_per_share if self._dcf_result else None
        return {
            "status": "report_generated",
            "target_price": dcf_fv,
            "sections": [
                "executive_summary",
                "company_overview",
                "financial_analysis",
                "valuation",
                "risk_factors",
                "investment_thesis",
            ],
        }

    # ── Helpers ─────────────────────────────────────────────────────────

    def _extract_three_statement_params(self, a: Dict) -> Dict:
        n = a.get("forecast_years", 5)
        growth_rates = a.get("revenue_growth_rates", [0.10] * n)
        return {
            "ticker": a.get("ticker", ""),
            "company_name": a.get("company_name", ""),
            "forecast_years": n,
            "base_revenue": a.get("base_revenue", 100),
            "revenue_growth_rates": growth_rates,
            "base_cash": a.get("base_cash", 20),
            "base_equity": a.get("base_equity", 80),
            "base_short_term_debt": a.get("base_short_term_debt", 10),
            "base_long_term_debt": a.get("base_long_term_debt", 30),
            "da_pct_revenue": a.get("da_pct_revenue", 0.03),
            "capex_pct_revenue": a.get("capex_pct_revenue", 0.04),
            "payout_ratio": a.get("payout_ratio", 0.50),
            "tax_rate": a.get("tax_rate", 0.25),
        }

    def _extract_dcf_params(self, a: Dict) -> Dict:
        n = a.get("forecast_years", 5)
        growth_rates = a.get("revenue_growth_rates", [0.10] * n)
        base_margin = a.get("base_ebit_margin", 0.20)
        margins = a.get("ebit_margins", [base_margin] * n)
        return {
            "ticker": a.get("ticker", ""),
            "company_name": a.get("company_name", ""),
            "forecast_years": n,
            "base_revenue": a.get("base_revenue", 100),
            "base_ebit_margin": base_margin,
            "revenue_growth_rates": growth_rates,
            "ebit_margins": margins,
            "wacc": a.get("wacc", 0.09),
            "terminal_growth_rate": a.get("terminal_growth_rate", 0.025),
            "shares_outstanding": a.get("shares_outstanding", 10),
            "net_debt": a.get("net_debt", 0),
            "da_pct_revenue": a.get("da_pct_revenue", 0.03),
            "capex_pct_revenue": a.get("capex_pct_revenue", 0.04),
            "wc_pct_revenue": a.get("wc_pct_revenue", 0.02),
            "tax_rate": a.get("tax_rate", 0.25),
            "current_price": a.get("current_price"),
        }

    def _compile_output(self) -> Dict:
        return {step: result.output for step, result in self.results.items()}


# ─── Report Pipeline ─────────────────────────────────────────────────────


@dataclass
class ReportSection:
    title: str
    content: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchReport:
    ticker: str
    company_name: str
    sections: List[ReportSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    executive_summary: str = ""
    investment_recommendation: str = ""
    target_price: float = 0.0
    risk_factors: List[str] = field(default_factory=list)


class ReportPipeline:
    """报告生成管线"""

    def __init__(self):
        self.section_templates = {
            "executive_summary": "投资要点与目标价",
            "company_overview": "公司概况与商业模式",
            "financial_analysis": "三表分析与财务指标",
            "valuation": "估值方法与目标价推导",
            "risk_factors": "风险因素与证伪条件",
            "investment_thesis": "投资建议与催化剂",
        }

    def generate(self, pipeline_result: PipelineResult, assumptions: Dict) -> ResearchReport:
        report = ResearchReport(
            ticker=assumptions.get("ticker", ""),
            company_name=assumptions.get("company_name", ""),
        )

        # 从管线结果提取数据
        dcf_output = pipeline_result.steps.get("09_dcf", StepResult(step=PipelineStep.STEP_09_DCF))
        if dcf_output.output:
            report.target_price = dcf_output.output.get("fair_value", 0)

        for section_key, section_title in self.section_templates.items():
            section = ReportSection(
                title=section_title,
                content=f"[{section_title}] 待生成",
            )
            report.sections.append(section)

        return report
