"""
情景分析引擎 — 乐观/基准/悲观三情景 DCF 加权估值。
每个情景独立运行简化 DCF，最终按概率加权。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.irongate import GateReport, IronGateEngine
from engine.precision import D, PreciseValuation, dto_float
from engine.schemas import ScenarioAssumptions, ScenarioDetail


@dataclass
class ScenarioResult:
    """情景分析结果"""

    scenario_prices: Dict[str, float] = field(default_factory=dict)
    # {"bull": 52.3, "base": 41.0, "bear": 28.5}

    scenario_details: Dict[str, dict] = field(default_factory=dict)
    # {"bull": {fcf_projections, terminal_value, tv_pct, ...}, ...}

    weighted_target: float = 0.0
    upside_pct: float = 0.0
    downside_pct: float = 0.0
    risk_reward: float = 0.0

    confidence: str = "medium"
    warnings: List[str] = field(default_factory=list)
    gate_report: Optional[GateReport] = None


class ScenarioEngine:
    """情景分析引擎 — Decimal 精度"""

    def __init__(self, assumptions: ScenarioAssumptions, skip_gates: bool = False) -> None:
        self.a = assumptions
        self.gate_report: Optional[GateReport] = None
        self.provenance = PreciseValuation()

        if not skip_gates:
            gate = IronGateEngine()
            self.gate_report = gate.validate_scenario(assumptions)
            if not self.gate_report.passed:
                errs = "; ".join(r.message for r in self.gate_report.errors)
                raise ValueError(f"IronGate Scenario 校验失败:\n{errs}")

    def run(self) -> ScenarioResult:
        a = self.a
        result = ScenarioResult(gate_report=self.gate_report)

        for name, detail in [("bull", a.bull), ("base", a.base), ("bear", a.bear)]:
            tp, details = self._run_scenario_dcf(name, detail)
            result.scenario_prices[name] = round(tp, 2)
            result.scenario_details[name] = details

        # 加权目标价 (Decimal)
        w_target = (
            D(result.scenario_prices["bull"]) * D(a.bull.probability)
            + D(result.scenario_prices["base"]) * D(a.base.probability)
            + D(result.scenario_prices["bear"]) * D(a.bear.probability)
        )
        result.weighted_target = dto_float(w_target)

        result.upside_pct = round((result.scenario_prices["bull"] / a.base_price - 1) * 100, 1)
        result.downside_pct = round((result.scenario_prices["bear"] / a.base_price - 1) * 100, 1)

        if result.downside_pct != 0:
            result.risk_reward = round(abs(result.upside_pct / result.downside_pct), 2)

        spread = result.scenario_prices["bull"] / result.scenario_prices["bear"]
        if spread > 3.0:
            result.confidence = "low"
            result.warnings.append(f"乐观/悲观价差 {spread:.1f}x > 3x")
        elif spread > 2.0:
            result.confidence = "medium"
        else:
            result.confidence = "high"

        return result

    def _run_scenario_dcf(self, name: str, detail: ScenarioDetail) -> tuple[float, dict]:
        """对单个情景运行简化 DCF — Decimal 精度"""
        a = self.a
        details: Dict = {}

        base_rev = D(a.base_revenue or 100.0)
        wacc = D(a.wacc)
        tax = D(a.tax_rate)
        net_debt = D(a.net_debt)

        # 逐年推演 (Decimal)
        fcf_list: list = []
        curr_rev = base_rev
        for i in range(a.projection_years):
            growth = D(detail.revenue_growth_rates[min(i, len(detail.revenue_growth_rates) - 1)])
            curr_rev = curr_rev * (D(1) + growth)
            ebit = curr_rev * D(detail.operating_margin)
            nopat = ebit * (D(1) - tax)
            fcf_list.append(nopat)

        # 终值 (Decimal)
        terminal_g = D(detail.terminal_growth)
        if fcf_list and wacc > terminal_g:
            last_fcf = fcf_list[-1]
            tv_fcf = last_fcf * (D(1) + terminal_g)
            tv = tv_fcf / (wacc - terminal_g)
            details["terminal_method"] = "ggm"
        elif fcf_list:
            tv = fcf_list[-1] * D(15)
            details["terminal_method"] = "exit_multiple_fallback"
        else:
            tv = D(0)

        # 折现 (Decimal)
        sum_pv = sum(f / ((D(1) + wacc) ** (i + 1)) for i, f in enumerate(fcf_list))
        tv_pv = tv / ((D(1) + wacc) ** a.projection_years)

        ev = sum_pv + tv_pv
        equity = ev - net_debt
        shares = D(a.total_shares or 10.0)
        tp = dto_float(equity / shares)

        details.update(
            {
                "revenue_final": dto_float(curr_rev),
                "fcf_final": dto_float(fcf_list[-1]) if fcf_list else 0,
                "sum_pv_fcf": round(dto_float(sum_pv), 2),
                "terminal_value": round(dto_float(tv), 2),
                "tv_pv": round(dto_float(tv_pv), 2),
                "tv_pct": round(dto_float(tv_pv / ev), 3) if ev > 0 else 0,
                "enterprise_value": round(dto_float(ev), 2),
                "equity_value": round(dto_float(equity), 2),
                "target_price": round(tp, 2),
                "probability": detail.probability,
            }
        )

        return tp, details
