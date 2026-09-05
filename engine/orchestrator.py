"""
16-Step IB-Grade Orchestrator + Report Pipeline。
参考 dashboard-package: IS→WC→CapexDA→Debt→Re-link→BS→CF→WACC→DCF→Scenarios→MC→Sensitivity→Tornado→Comps→Excel→PDF
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


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
    """单步结果"""

    step: PipelineStep
    status: str = "pending"  # pending / running / completed / failed
    duration_ms: float = 0.0
    output: Any = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """完整管线结果"""

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
            if result.warnings:
                for w in result.warnings:
                    lines.append(f"    WARN: {w}")
            if result.errors:
                for e in result.errors:
                    lines.append(f"    ERR: {e}")
        return "\n".join(lines)


class IBGradeOrchestrator:
    """16-Step IB-Grade Pipeline Orchestrator"""

    def __init__(self):
        self.steps: List[PipelineStep] = list(PipelineStep)
        self.results: Dict[str, StepResult] = {}

    def run(self, assumptions: Dict[str, Any]) -> PipelineResult:
        """运行完整 16 步管线"""
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
        """执行单步"""
        # 这里是简化实现，实际会调用各个引擎
        step_handlers = {
            PipelineStep.STEP_01_INCOME_STATEMENT: self._step_income_statement,
            PipelineStep.STEP_02_WORKING_CAPITAL: self._step_working_capital,
            PipelineStep.STEP_03_CAPEX_DA: self._step_capex_da,
            PipelineStep.STEP_04_DEBT_SCHEDULE: self._step_debt_schedule,
            PipelineStep.STEP_05_RELINK_IS: self._step_relink_is,
            PipelineStep.STEP_06_BALANCE_SHEET: self._step_balance_sheet,
            PipelineStep.STEP_07_CASH_FLOW: self._step_cash_flow,
            PipelineStep.STEP_08_WACC: self._step_wacc,
            PipelineStep.STEP_09_DCF: self._step_dcf,
            PipelineStep.STEP_10_SCENARIOS: self._step_scenarios,
            PipelineStep.STEP_11_MONTE_CARLO: self._step_monte_carlo,
            PipelineStep.STEP_12_SENSITIVITY: self._step_sensitivity,
            PipelineStep.STEP_13_TORNADO: self._step_tornado,
            PipelineStep.STEP_14_COMPS: self._step_comps,
            PipelineStep.STEP_15_EXCEL: self._step_excel,
            PipelineStep.STEP_16_REPORT: self._step_report,
        }
        handler = step_handlers.get(step, lambda a: None)
        return handler(assumptions)

    def _step_income_statement(self, a: Dict) -> Dict:
        return {"status": "income_statement_built", "revenue": a.get("base_revenue", 0)}

    def _step_working_capital(self, a: Dict) -> Dict:
        return {"status": "working_capital_computed"}

    def _step_capex_da(self, a: Dict) -> Dict:
        return {"status": "capex_da_computed"}

    def _step_debt_schedule(self, a: Dict) -> Dict:
        return {"status": "debt_schedule_built"}

    def _step_relink_is(self, a: Dict) -> Dict:
        return {"status": "is_relinked"}

    def _step_balance_sheet(self, a: Dict) -> Dict:
        return {"status": "balance_sheet_built"}

    def _step_cash_flow(self, a: Dict) -> Dict:
        return {"status": "cash_flow_built"}

    def _step_wacc(self, a: Dict) -> Dict:
        return {"status": "wacc_computed", "wacc": a.get("wacc", 0.09)}

    def _step_dcf(self, a: Dict) -> Dict:
        return {"status": "dcf_computed"}

    def _step_scenarios(self, a: Dict) -> Dict:
        return {"status": "scenarios_computed"}

    def _step_monte_carlo(self, a: Dict) -> Dict:
        return {"status": "monte_carlo_completed"}

    def _step_sensitivity(self, a: Dict) -> Dict:
        return {"status": "sensitivity_computed"}

    def _step_tornado(self, a: Dict) -> Dict:
        return {"status": "tornado_computed"}

    def _step_comps(self, a: Dict) -> Dict:
        return {"status": "comps_computed"}

    def _step_excel(self, a: Dict) -> Dict:
        return {"status": "excel_exported"}

    def _step_report(self, a: Dict) -> Dict:
        return {"status": "report_generated"}

    def _compile_output(self) -> Dict:
        return {step: result.output for step, result in self.results.items()}


# ─── Report Pipeline ────────────────────────────────────────────────────────


@dataclass
class ReportSection:
    """报告章节"""

    title: str
    content: str
    data: Dict[str, Any] = field(default_factory=dict)
    charts: List[str] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)


@dataclass
class ResearchReport:
    """研究报告"""

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
            "industry_analysis": "行业格局与竞争态势",
            "financial_analysis": "三表分析与财务指标",
            "valuation": "估值方法与目标价推导",
            "risk_factors": "风险因素与证伪条件",
            "investment_thesis": "投资建议与催化剂",
        }

    def generate(self, pipeline_result: PipelineResult, assumptions: Dict) -> ResearchReport:
        """从管线结果生成报告"""
        report = ResearchReport(
            ticker=assumptions.get("ticker", ""),
            company_name=assumptions.get("company_name", ""),
        )

        for section_key, section_title in self.section_templates.items():
            section = ReportSection(
                title=section_title,
                content=f"[{section_title}] 待生成",
            )
            report.sections.append(section)

        return report
