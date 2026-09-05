"""
情景分析引擎 — 乐观/基准/悲观三情景 DCF 加权估值。
每个情景独立运行简化 DCF，最终按概率加权。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.irongate import GateReport, IronGateEngine
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
    """情景分析引擎"""

    def __init__(self, assumptions: ScenarioAssumptions, skip_gates: bool = False) -> None:
        self.a = assumptions
        self.gate_report: Optional[GateReport] = None

        if not skip_gates:
            gate = IronGateEngine()
            self.gate_report = gate.validate_scenario(assumptions)
            if not self.gate_report.passed:
                errs = "; ".join(r.message for r in self.gate_report.errors)
                raise ValueError(f"IronGate Scenario 校验失败:\n{errs}")

    def run(self) -> ScenarioResult:
        a = self.a
        result = ScenarioResult(gate_report=self.gate_report)

        # 对每个情景运行简化 DCF
        for name, detail in [("bull", a.bull), ("base", a.base), ("bear", a.bear)]:
            tp, details = self._run_scenario_dcf(name, detail)
            result.scenario_prices[name] = round(tp, 2)
            result.scenario_details[name] = details

        # 加权目标价
        result.weighted_target = round(
            result.scenario_prices["bull"] * a.bull.probability
            + result.scenario_prices["base"] * a.base.probability
            + result.scenario_prices["bear"] * a.bear.probability,
            2,
        )

        # 上行/下行
        result.upside_pct = round((result.scenario_prices["bull"] / a.base_price - 1) * 100, 1)
        result.downside_pct = round((result.scenario_prices["bear"] / a.base_price - 1) * 100, 1)

        # 风险收益比
        if result.downside_pct != 0:
            result.risk_reward = round(abs(result.upside_pct / result.downside_pct), 2)

        # 置信度
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
        """对单个情景运行简化 DCF，返回 (target_price, details_dict)"""
        a = self.a
        details: Dict = {}

        # 基期营收：使用 base_revenue 或默认 100 亿
        base_rev = a.base_revenue or 100.0

        # 逐年推演
        fcf_list: List[float] = []
        curr_rev = base_rev
        for i in range(a.projection_years):
            if i < len(detail.revenue_growth_rates):
                growth = detail.revenue_growth_rates[i]
            else:
                # 超出假设的部分，线性衰减到最后一个假设值
                growth = detail.revenue_growth_rates[-1]

            curr_rev = curr_rev * (1 + growth)
            ebit = curr_rev * detail.operating_margin
            nopat = ebit * (1 - a.tax_rate)
            # 简化：FCF ≈ NOPAT（无 D&A/CapEx/WC 细分）
            fcf_list.append(nopat)

        # 终值
        if fcf_list:
            last_fcf = fcf_list[-1]
            if a.wacc > detail.terminal_growth:
                tv_fcf = last_fcf * (1 + detail.terminal_growth)
                tv = tv_fcf / (a.wacc - detail.terminal_growth)
            else:
                # 退路：15x NOPAT
                tv = last_fcf * 15.0
                details["terminal_method"] = "exit_multiple_fallback"
        else:
            tv = 0.0

        # 折现
        sum_pv = sum(fcf / ((1 + a.wacc) ** (i + 1)) for i, fcf in enumerate(fcf_list))
        tv_pv = tv / ((1 + a.wacc) ** a.projection_years)

        ev = sum_pv + tv_pv
        equity = ev - a.net_debt
        shares = a.total_shares or 10.0
        tp = equity / shares

        details.update(
            {
                "revenue_final": curr_rev,
                "fcf_final": fcf_list[-1] if fcf_list else 0,
                "sum_pv_fcf": round(sum_pv, 2),
                "terminal_value": round(tv, 2),
                "tv_pv": round(tv_pv, 2),
                "tv_pct": round(tv_pv / ev, 3) if ev > 0 else 0,
                "enterprise_value": round(ev, 2),
                "equity_value": round(equity, 2),
                "target_price": round(tp, 2),
                "probability": detail.probability,
            }
        )

        return tp, details
