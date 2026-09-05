"""
FCFF 路径选择 + 市场隐含增长率求解器 + 结构化诊断。
参考 FP-DCF: 可追溯的 FCFF 路径、市场隐含 g、机器可读诊断。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class FCFFPath(str, Enum):
    """FCFF 计算路径"""

    EBIAT = "ebiat"  # FCFF = EBIT × (1-T) + D&A - Capex - ΔWC
    CFO_ADJUSTED = "cfo_adjusted"  # FCFF = CFO + Interest×(1-T) - Capex


@dataclass
class FCFFPathResult:
    """FCFF 路径计算结果"""

    path_used: FCFFPath
    ebit: float = 0.0
    tax_on_ebit: float = 0.0
    ebiat: float = 0.0
    da: float = 0.0
    capex: float = 0.0
    wc_change: float = 0.0
    fcff: float = 0.0
    # CFO 路径明细
    cfo: Optional[float] = None
    interest_after_tax: Optional[float] = None
    fcff_from_cfo: Optional[float] = None
    # 两条路径差异
    path_diff: Optional[float] = None
    path_diff_pct: Optional[float] = None


@dataclass
class MarketImpliedResult:
    """市场隐含增长率结果"""

    current_price: float = 0.0
    implied_ev: float = 0.0
    implied_fcf: float = 0.0
    implied_growth: float = 0.0
    implied_wacc: float = 0.0
    years_to_converge: int = 10
    growth_trajectory: List[float] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class FCFFPathEngine:
    """FCFF 路径选择引擎"""

    def compute_both_paths(
        self,
        ebit: float,
        tax_rate: float,
        da: float,
        capex: float,
        wc_change: float,
        cfo: Optional[float] = None,
        interest_expense: Optional[float] = None,
    ) -> FCFFPathResult:
        """同时计算两条路径，对比差异"""
        result = FCFFPathResult(path_used=FCFFPath.EBIAT)

        # EBIAT 路径
        result.ebit = ebit
        result.tax_on_ebit = ebit * tax_rate
        result.ebiat = ebit * (1 - tax_rate)
        result.da = da
        result.capex = capex
        result.wc_change = wc_change
        result.fcff = result.ebiat + da - capex - wc_change

        # CFO 路径（如果提供了 CFO）
        if cfo is not None and interest_expense is not None:
            result.cfo = cfo
            result.interest_after_tax = interest_expense * (1 - tax_rate)
            result.fcff_from_cfo = cfo + result.interest_after_tax - capex

            # 计算差异
            result.path_diff = result.fcff - result.fcff_from_cfo
            if result.fcff != 0:
                result.path_diff_pct = abs(result.path_diff) / abs(result.fcff) * 100

        return result


class MarketImpliedSolver:
    """市场隐含增长率求解器"""

    def solve(
        self,
        current_price: float,
        shares_outstanding: float,
        net_debt: float,
        current_fcf: float,
        wacc: float,
        terminal_growth: float = 0.03,
        forecast_years: int = 10,
        tolerance: float = 0.001,
        max_iterations: int = 100,
    ) -> MarketImpliedResult:
        """从当前价格倒算隐含增长率"""
        result = MarketImpliedResult(
            current_price=current_price,
            implied_wacc=wacc,
        )

        if current_price <= 0 or shares_outstanding <= 0:
            result.warnings.append("价格或股本无效")
            return result

        if current_fcf <= 0:
            result.warnings.append("FCF 为负，无法求解隐含增长率")
            return result

        # 目标企业价值
        target_ev = current_price * shares_outstanding + net_debt
        result.implied_ev = target_ev
        result.implied_fcf = current_fcf

        # 二分法求解隐含增长率
        low, high = -0.50, 1.0  # 增长率搜索范围
        implied_g = 0.0

        for _ in range(max_iterations):
            mid = (low + high) / 2
            computed_ev = self._compute_ev_from_growth(current_fcf, mid, wacc, terminal_growth, forecast_years)

            if abs(computed_ev - target_ev) / target_ev < tolerance:
                implied_g = mid
                break

            if computed_ev < target_ev:
                low = mid
            else:
                high = mid

        result.implied_growth = implied_g

        # 生成增长轨迹（从 implied_g 线性衰减到 terminal_growth）
        result.growth_trajectory = [
            implied_g - (implied_g - terminal_growth) * i / forecast_years for i in range(forecast_years)
        ]

        return result

    def _compute_ev_from_growth(
        self,
        base_fcf: float,
        growth_rate: float,
        wacc: float,
        terminal_growth: float,
        years: int,
    ) -> float:
        """从增长率计算企业价值"""
        fcf = base_fcf
        pv_fcf = 0.0

        for i in range(years):
            fcf *= 1 + growth_rate
            pv_fcf += fcf / ((1 + wacc) ** (i + 1))

        # Terminal value
        tv_fcf = fcf * (1 + terminal_growth)
        tv = tv_fcf / (wacc - terminal_growth)
        tv_pv = tv / ((1 + wacc) ** years)

        return pv_fcf + tv_pv


# ─── Structured Diagnostics ─────────────────────────────────────────────────


class DiagnosticLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Diagnostic:
    """单条诊断信息"""

    code: str
    level: DiagnosticLevel
    message: str
    source: str = ""
    value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class DiagnosticReport:
    """诊断报告"""

    diagnostics: List[Diagnostic] = field(default_factory=list)
    source_label: str = ""
    model_used: str = ""
    effective_model: str = ""

    @property
    def has_errors(self) -> bool:
        return any(d.level == DiagnosticLevel.ERROR for d in self.diagnostics)

    @property
    def has_warnings(self) -> bool:
        return any(d.level == DiagnosticLevel.WARNING for d in self.diagnostics)

    def to_dict(self) -> dict:
        return {
            "source_label": self.source_label,
            "model_used": self.model_used,
            "effective_model": self.effective_model,
            "diagnostics": [
                {
                    "code": d.code,
                    "level": d.level.value,
                    "message": d.message,
                    "source": d.source,
                    "value": d.value,
                    "threshold": d.threshold,
                }
                for d in self.diagnostics
            ],
        }


class DiagnosticEngine:
    """诊断引擎 — 生成机器可读的诊断报告"""

    def check_wacc合理性(self, wacc: float, risk_free: float, erp: float, beta: float) -> Diagnostic:
        expected = risk_free + beta * erp
        diff = abs(wacc - expected)
        if diff > 0.03:
            return Diagnostic(
                "WACC-01",
                DiagnosticLevel.WARNING,
                f"WACC ({wacc:.2%}) 偏离 CAPM 预期 ({expected:.2%}) 超过 3pp",
                "wacc_consistency",
                wacc,
                expected,
            )
        return Diagnostic("WACC-01", DiagnosticLevel.INFO, "WACC 与 CAPM 一致", "wacc_consistency")

    def check_terminal_value_pct(self, tv_pct: float) -> Diagnostic:
        if tv_pct > 0.80:
            return Diagnostic(
                "TV-01",
                DiagnosticLevel.WARNING,
                f"终值占比 ({tv_pct:.1%}) > 80%，模型过度依赖永续假设",
                "tv_sensitivity",
                tv_pct,
                0.80,
            )
        return Diagnostic("TV-01", DiagnosticLevel.INFO, f"终值占比 ({tv_pct:.1%}) 合理")

    def check_growth_convergence(self, growth_rates: List[float], terminal_g: float) -> Diagnostic:
        if growth_rates and growth_rates[-1] > terminal_g + 0.02:
            return Diagnostic(
                "GROWTH-01",
                DiagnosticLevel.WARNING,
                f"末期增速 ({growth_rates[-1]:.2%}) 显著高于永续增长率 ({terminal_g:.2%})",
                "growth_convergence",
                growth_rates[-1],
                terminal_g,
            )
        return Diagnostic("GROWTH-01", DiagnosticLevel.INFO, "增速收敛合理")

    def check_margin_stability(self, margins: List[float]) -> Diagnostic:
        if len(margins) >= 2:
            spread = max(margins) - min(margins)
            if spread > 0.10:
                return Diagnostic(
                    "MARGIN-01",
                    DiagnosticLevel.WARNING,
                    f"利润率波动 ({spread:.1%}) 过大，需验证假设",
                    "margin_stability",
                    spread,
                    0.10,
                )
        return Diagnostic("MARGIN-01", DiagnosticLevel.INFO, "利润率稳定")

    def check_debt_sanity(self, net_debt: float, revenue: float) -> Diagnostic:
        if revenue > 0 and abs(net_debt) > revenue * 5:
            return Diagnostic(
                "DEBT-01",
                DiagnosticLevel.ERROR,
                f"净负债 ({net_debt:.2f}亿) 超过营收 5 倍",
                "debt_sanity",
                net_debt,
                revenue * 5,
            )
        return Diagnostic("DEBT-01", DiagnosticLevel.INFO, "负债水平合理")

    def build_report(
        self,
        wacc: float = 0.0,
        risk_free: float = 0.025,
        erp: float = 0.065,
        beta: float = 1.0,
        tv_pct: float = 0.0,
        growth_rates: Optional[List[float]] = None,
        terminal_g: float = 0.03,
        margins: Optional[List[float]] = None,
        net_debt: float = 0.0,
        revenue: float = 0.0,
        model_used: str = "DCF",
    ) -> DiagnosticReport:
        """构建完整诊断报告"""
        report = DiagnosticReport(model_used=model_used, effective_model=model_used)

        if wacc > 0:
            report.diagnostics.append(self.check_wacc合理性(wacc, risk_free, erp, beta))
        if tv_pct > 0:
            report.diagnostics.append(self.check_terminal_value_pct(tv_pct))
        if growth_rates:
            report.diagnostics.append(self.check_growth_convergence(growth_rates, terminal_g))
        if margins:
            report.diagnostics.append(self.check_margin_stability(margins))
        if revenue > 0:
            report.diagnostics.append(self.check_debt_sanity(net_debt, revenue))

        return report
