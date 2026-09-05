"""
IronGate 预检网关 — 在计算前拦截畸形假设。
分为 L1 结构边界、L2 财务逻辑、L3 估值畸变三级。

与 pipeline/iron_gate.py 的关系：
  - pipeline IronGate 检查报告文本（事后）
  - engine IronGate 检查输入假设（事前）
  - 两层互补，不替代
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Forward reference for ThreeStatementAssumptions
from typing import TYPE_CHECKING, Callable, List

from engine.schemas import (
    ComparableAssumptions,
    DCFAssumptions,
    ScenarioAssumptions,
    SOTPAssumptions,
)

if TYPE_CHECKING:
    from engine.three_statement import ThreeStatementAssumptions

# ─── Gate Result ────────────────────────────────────────────────────────────


@dataclass
class GateResult:
    gate_id: str
    level: str  # L1 / L2 / L3
    passed: bool
    message: str
    severity: str = "error"  # error / warning


@dataclass
class GateReport:
    results: List[GateResult] = field(default_factory=list)
    gate_version: str = "engine-v1.0.0"

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results if r.severity == "error")

    @property
    def errors(self) -> List[GateResult]:
        return [r for r in self.results if not r.passed and r.severity == "error"]

    @property
    def warnings(self) -> List[GateResult]:
        return [r for r in self.results if not r.passed and r.severity == "warning"]

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        errs = len(self.errors)
        warns = len(self.warnings)
        status = "PASS" if self.passed else "FAIL"
        lines = [f"[IronGate Engine] {status} ({passed}/{total} passed)"]
        for r in self.results:
            mark = "✓" if r.passed else "✗"
            lines.append(f"  {mark} [{r.level}] {r.gate_id}: {r.message}")
        if errs:
            lines.append(f"\n  BLOCKED: {errs} error(s) must be fixed before computation.")
        if warns:
            lines.append(f"  WARNINGS: {warns} (computation will proceed)")
        return "\n".join(lines)


# ─── Gate Decorator ─────────────────────────────────────────────────────────


class IronGateEngine:
    """引擎级 IronGate：校验输入假设的结构与逻辑合理性"""

    def __init__(self) -> None:
        self._dcf_gates: List[Callable] = []
        self._comparable_gates: List[Callable] = []
        self._scenario_gates: List[Callable] = []
        self._sotp_gates: List[Callable] = []
        self._register_all()

    def _register_all(self) -> None:
        self._dcf_gates = [
            self._g_dcf_01_forecast_length,
            self._g_dcf_02_wacc_gt_growth,
            self._g_dcf_03_terminal_growth_cap,
            self._g_dcf_04_growth_sanity,
            self._g_dcf_05_margin_range,
            self._g_dcf_06_tax_rate,
            self._g_dcf_07_wacc_range,
            self._g_dcf_08_positive_revenue,
            self._g_dcf_09_positive_shares,
            self._g_dcf_10_net_debt_sanity,
        ]
        self._comparable_gates = [
            self._g_comp_01_peer_count,
            self._g_comp_02_pe_positive,
            self._g_comp_03_eps_for_pe,
        ]
        self._scenario_gates = [
            self._g_scn_01_probability_sum,
            self._g_scn_02_monotonicity,
            self._g_scn_03_extreme_spread,
            self._g_scn_04_growth_sanity,
        ]
        self._sotp_gates = [
            self._g_sotp_01_segments_exist,
            self._g_sotp_02_multiples_positive,
            self._g_sotp_03_shares_positive,
        ]

    # ── DCF Gates ───────────────────────────────────────────────────────

    def _g_dcf_01_forecast_length(self, a: DCFAssumptions) -> GateResult:
        ok = len(a.revenue_growth_rates) == a.forecast_years and len(a.ebit_margins) == a.forecast_years
        return GateResult(
            "DCF-01",
            "L1",
            ok,
            f"预测序列长度 = {len(a.revenue_growth_rates)}/{len(a.ebit_margins)}，预测期 = {a.forecast_years}"
            if not ok
            else "预测序列长度与预测期匹配",
        )

    def _g_dcf_02_wacc_gt_growth(self, a: DCFAssumptions) -> GateResult:
        ok = a.wacc > a.terminal_growth_rate
        return GateResult(
            "DCF-02",
            "L2",
            ok,
            f"WACC ({a.wacc:.2%}) 必须 > 永续增长率 g ({a.terminal_growth_rate:.2%})"
            if not ok
            else f"WACC ({a.wacc:.2%}) > g ({a.terminal_growth_rate:.2%}) ✓",
        )

    def _g_dcf_03_terminal_growth_cap(self, a: DCFAssumptions) -> GateResult:
        ok = a.terminal_growth_rate <= 0.045
        return GateResult(
            "DCF-03",
            "L2",
            ok,
            f"永续增长率 ({a.terminal_growth_rate:.2%}) 超过宏观上限 4.5%"
            if not ok
            else f"永续增长率 ({a.terminal_growth_rate:.2%}) 在合理范围内",
        )

    def _g_dcf_04_growth_sanity(self, a: DCFAssumptions) -> GateResult:
        extreme = [(i, g) for i, g in enumerate(a.revenue_growth_rates) if abs(g) > 1.5]
        ok = len(extreme) == 0
        details = ", ".join(f"第{i + 1}年={g:.0%}" for i, g in extreme) if extreme else ""
        return GateResult(
            "DCF-04", "L2", ok, f"极端增速: {details}（>150%，需人工复核）" if not ok else "增速序列在合理范围内"
        )

    def _g_dcf_05_margin_range(self, a: DCFAssumptions) -> GateResult:
        bad = [(i, m) for i, m in enumerate(a.ebit_margins) if m < -0.30 or m > 0.80]
        ok = len(bad) == 0
        details = ", ".join(f"第{i + 1}年={m:.0%}" for i, m in bad) if bad else ""
        return GateResult("DCF-05", "L1", ok, f"EBIT 利润率异常: {details}" if not ok else "EBIT 利润率在合理范围内")

    def _g_dcf_06_tax_rate(self, a: DCFAssumptions) -> GateResult:
        ok = 0.0 <= a.tax_rate <= 0.50
        return GateResult(
            "DCF-06",
            "L1",
            ok,
            f"税率 ({a.tax_rate:.2%}) 超出合理范围 [0%, 50%]" if not ok else f"税率 ({a.tax_rate:.2%}) ✓",
        )

    def _g_dcf_07_wacc_range(self, a: DCFAssumptions) -> GateResult:
        ok = 0.01 < a.wacc < 0.30
        return GateResult(
            "DCF-07", "L1", ok, f"WACC ({a.wacc:.2%}) 超出合理范围 (1%, 30%)" if not ok else f"WACC ({a.wacc:.2%}) ✓"
        )

    def _g_dcf_08_positive_revenue(self, a: DCFAssumptions) -> GateResult:
        ok = a.base_revenue > 0
        return GateResult(
            "DCF-08",
            "L1",
            ok,
            f"基期营收 ({a.base_revenue}) 必须为正" if not ok else f"基期营收 ({a.base_revenue:.2f}亿) ✓",
        )

    def _g_dcf_09_positive_shares(self, a: DCFAssumptions) -> GateResult:
        ok = a.shares_outstanding > 0
        return GateResult(
            "DCF-09",
            "L1",
            ok,
            f"股本 ({a.shares_outstanding}) 必须为正" if not ok else f"股本 ({a.shares_outstanding:.2f}亿股) ✓",
        )

    def _g_dcf_10_net_debt_sanity(self, a: DCFAssumptions) -> GateResult:
        # 净负债不应超过基期营收的 5 倍（极端杠杆）
        if a.base_revenue > 0 and abs(a.net_debt) > a.base_revenue * 5:
            return GateResult("DCF-10", "L2", False, f"净负债 ({a.net_debt:.2f}亿) 超过基期营收 5 倍，杠杆异常")
        return GateResult("DCF-10", "L2", True, "净负债在合理范围内")

    # ── Comparable Gates ────────────────────────────────────────────────

    def _g_comp_01_peer_count(self, a: ComparableAssumptions) -> GateResult:
        ok = len(a.peer_pe_ratios) >= 3
        return GateResult(
            "COMP-01",
            "L1",
            ok,
            f"可比公司仅 {len(a.peer_pe_ratios)} 家 < 3，可比性不足"
            if not ok
            else f"可比公司 {len(a.peer_pe_ratios)} 家 ✓",
        )

    def _g_comp_02_pe_positive(self, a: ComparableAssumptions) -> GateResult:
        neg = [i for i, pe in enumerate(a.peer_pe_ratios) if pe <= 0]
        ok = len(neg) == 0
        return GateResult(
            "COMP-02", "L1", ok, f"可比公司 PE 为非正数: 索引 {neg}" if not ok else "所有可比公司 PE 为正 ✓"
        )

    def _g_comp_03_eps_for_pe(self, a: ComparableAssumptions) -> GateResult:
        ok = a.company_eps > 0
        return GateResult(
            "COMP-03",
            "L2",
            ok,
            f"标的 EPS ({a.company_eps}) ≤ 0，PE 估值失真" if not ok else f"标的 EPS ({a.company_eps:.2f}) ✓",
        )

    # ── Scenario Gates ──────────────────────────────────────────────────

    def _g_scn_01_probability_sum(self, a: ScenarioAssumptions) -> GateResult:
        total = a.bull.probability + a.base.probability + a.bear.probability
        ok = abs(total - 1.0) <= 0.02
        return GateResult(
            "SCN-01", "L1", ok, f"概率之和 ({total:.2%}) 偏离 100% 超过 2%" if not ok else f"概率之和 ({total:.2%}) ✓"
        )

    def _g_scn_02_monotonicity(self, a: ScenarioAssumptions) -> GateResult:
        ok = a.bull.operating_margin >= a.base.operating_margin >= a.bear.operating_margin
        return GateResult(
            "SCN-02",
            "L2",
            ok,
            f"利润率未单调递减: bull={a.bull.operating_margin:.0%} "
            f"base={a.base.operating_margin:.0%} bear={a.bear.operating_margin:.0%}"
            if not ok
            else "利润率单调递减 ✓",
        )

    def _g_scn_03_extreme_spread(self, a: ScenarioAssumptions) -> GateResult:
        if a.bear.operating_margin > 0:
            ratio = a.bull.operating_margin / a.bear.operating_margin
            ok = ratio < 5.0
            return GateResult(
                "SCN-03",
                "L2",
                ok,
                f"乐观/悲观利润率倍数 ({ratio:.1f}x) 过大" if not ok else f"乐观/悲观利润率倍数 ({ratio:.1f}x) ✓",
            )
        return GateResult("SCN-03", "L2", True, "悲观利润率为零，跳过倍数检查")

    def _g_scn_04_growth_sanity(self, a: ScenarioAssumptions) -> GateResult:
        all_rates = a.bull.revenue_growth_rates + a.base.revenue_growth_rates + a.bear.revenue_growth_rates
        extreme = [g for g in all_rates if abs(g) > 2.0]
        ok = len(extreme) == 0
        return GateResult(
            "SCN-04", "L2", ok, f"情景中存在极端增速 ({len(extreme)} 项 >200%)" if not ok else "情景增速在合理范围内"
        )

    # ── SOTP Gates ──────────────────────────────────────────────────────

    def _g_sotp_01_segments_exist(self, a: SOTPAssumptions) -> GateResult:
        ok = len(a.segments) >= 1
        return GateResult("SOTP-01", "L1", ok, "至少需要 1 个估值分部" if not ok else f"{len(a.segments)} 个分部 ✓")

    def _g_sotp_02_multiples_positive(self, a: SOTPAssumptions) -> GateResult:
        bad = [(i, s.name, s.peer_multiple) for i, s in enumerate(a.segments) if s.peer_multiple <= 0]
        ok = len(bad) == 0
        details = ", ".join(f"{name}={mult}" for _, name, mult in bad) if bad else ""
        return GateResult("SOTP-02", "L1", ok, f"分部倍数非正: {details}" if not ok else "所有分部倍数为正 ✓")

    def _g_sotp_03_shares_positive(self, a: SOTPAssumptions) -> GateResult:
        ok = a.total_shares > 0
        return GateResult(
            "SOTP-03",
            "L1",
            ok,
            f"总股本 ({a.total_shares}) 必须为正" if not ok else f"总股本 ({a.total_shares:.2f}亿股) ✓",
        )

    # ── Public API ──────────────────────────────────────────────────────

    def validate_dcf(self, a: DCFAssumptions) -> GateReport:
        report = GateReport()
        for gate_fn in self._dcf_gates:
            report.results.append(gate_fn(a))
        return report

    def validate_comparable(self, a: ComparableAssumptions) -> GateReport:
        report = GateReport()
        for gate_fn in self._comparable_gates:
            report.results.append(gate_fn(a))
        return report

    def validate_scenario(self, a: ScenarioAssumptions) -> GateReport:
        report = GateReport()
        for gate_fn in self._scenario_gates:
            report.results.append(gate_fn(a))
        return report

    def validate_sotp(self, a: SOTPAssumptions) -> GateReport:
        report = GateReport()
        for gate_fn in self._sotp_gates:
            report.results.append(gate_fn(a))
        return report

    # ── Three-Statement Gates ──────────────────────────────────────────────

    def validate_three_statement(self, a: "ThreeStatementAssumptions") -> GateReport:
        """三表联动假设校验"""
        report = GateReport()

        # TS-01: 预测期长度
        ok = len(a.revenue_growth_rates) == a.forecast_years
        report.results.append(
            GateResult(
                "TS-01",
                "L1",
                ok,
                f"revenue_growth_rates 长度 ({len(a.revenue_growth_rates)}) ≠ forecast_years ({a.forecast_years})"
                if not ok
                else "预测期长度匹配",
            )
        )

        # TS-02: 税率范围
        ok = 0.0 <= a.tax_rate <= 0.50
        report.results.append(
            GateResult(
                "TS-02",
                "L1",
                ok,
                f"税率 ({a.tax_rate:.2%}) 超出 [0%, 50%]" if not ok else f"税率 ({a.tax_rate:.2%}) ✓",
            )
        )

        # TS-03: 分红率范围
        ok = 0.0 <= a.payout_ratio <= 1.0
        report.results.append(
            GateResult(
                "TS-03",
                "L1",
                ok,
                f"分红率 ({a.payout_ratio:.2%}) 超出 [0%, 100%]" if not ok else f"分红率 ({a.payout_ratio:.2%}) ✓",
            )
        )

        # TS-04: 基期权益为正
        ok = a.base_equity > 0
        report.results.append(
            GateResult(
                "TS-04",
                "L1",
                ok,
                f"基期权益 ({a.base_equity:.2f}亿) 必须为正" if not ok else f"基期权益 ({a.base_equity:.2f}亿) ✓",
            )
        )

        # TS-05: 基期营收为正
        ok = a.base_revenue > 0
        report.results.append(
            GateResult(
                "TS-05",
                "L1",
                ok,
                f"基期营收 ({a.base_revenue:.2f}亿) 必须为正" if not ok else f"基期营收 ({a.base_revenue:.2f}亿) ✓",
            )
        )

        # TS-06: 资本支出 vs 折旧
        if a.capex_pct_revenue < a.da_pct_revenue:
            report.results.append(
                GateResult(
                    "TS-06",
                    "L2",
                    False,
                    f"资本支出占比 ({a.capex_pct_revenue:.2%}) < 折旧占比 ({a.da_pct_revenue:.2%})，企业可能在收缩",
                    severity="warning",
                )
            )
        else:
            report.results.append(GateResult("TS-06", "L2", True, "资本支出 ≥ 折旧 ✓"))

        # TS-07: 债务利率合理性
        if a.term_loan_rate > 0.20:
            report.results.append(
                GateResult(
                    "TS-07",
                    "L2",
                    False,
                    f"长期贷款利率 ({a.term_loan_rate:.2%}) 过高",
                    severity="warning",
                )
            )
        else:
            report.results.append(GateResult("TS-07", "L2", True, f"长期贷款利率 ({a.term_loan_rate:.2%}) ✓"))

        # TS-08: 增速合理性
        extreme = [g for g in a.revenue_growth_rates if abs(g) > 1.0]
        if extreme:
            report.results.append(
                GateResult(
                    "TS-08",
                    "L2",
                    False,
                    f"存在极端增速 ({len(extreme)} 项 >100%)",
                    severity="warning",
                )
            )
        else:
            report.results.append(GateResult("TS-08", "L2", True, "增速在合理范围内"))

        return report

    def validate_all(
        self,
        dcf: DCFAssumptions | None = None,
        comparable: ComparableAssumptions | None = None,
        scenario: ScenarioAssumptions | None = None,
        sotp: SOTPAssumptions | None = None,
    ) -> dict[str, GateReport]:
        reports = {}
        if dcf:
            reports["dcf"] = self.validate_dcf(dcf)
        if comparable:
            reports["comparable"] = self.validate_comparable(comparable)
        if scenario:
            reports["scenario"] = self.validate_scenario(scenario)
        if sotp:
            reports["sotp"] = self.validate_sotp(sotp)
        return reports
