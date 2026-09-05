"""
Reverse-DCF 求解器 — 从当前市值反推隐含增长率/利润率。
参考 Expectations Investing (Reis & Damodaran)。

核心能力:
1. 单变量求解: 给定 EV/WACC/FCF, 解隐含永续增长率 g
2. 双变量求解: 同时解 (FCF margin, growth)
3. 期望差距分析: 我们的假设 vs 市场隐含
4. 临界点分析: 价格下跌 X% 时隐含什么
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.precision import D, dto_float


@dataclass
class ReverseDCFResult:
    """Reverse-DCF 求解结果"""

    # 隐含值
    implied_growth_rate: float = 0.0
    implied_fcf_margin: float = 0.0
    implied_ev_ebitda: float = 0.0

    # 输入
    market_cap: float = 0.0
    enterprise_value: float = 0.0
    ev_to_fcf: float = 0.0

    # 期望差距
    our_growth: Optional[float] = None
    implied_growth: Optional[float] = None
    expectation_gap_pp: Optional[float] = None

    # 临界点
    price_drop_to_fair_value_pct: Optional[float] = None

    # 求解质量
    converged: bool = True
    iterations: int = 0
    residual: float = 0.0

    # 分解
    growth_contribution_pct: float = 0.0
    value_contribution_pct: float = 0.0
    quality_contribution_pct: float = 0.0

    warnings: list[str] = field(default_factory=list)


class ReverseDCFSolver:
    """Reverse-DCF 求解器 — Decimal 精度"""

    def __init__(
        self,
        current_price: float,
        shares_outstanding: float,
        net_debt: float = 0.0,
        fcf_ttm: Optional[float] = None,
        revenue_ttm: Optional[float] = None,
        ebit_ttm: Optional[float] = None,
        wacc: float = 0.10,
        terminal_growth_rate: float = 0.025,
        tax_rate: float = 0.25,
        forecast_years: int = 10,
    ):
        self.current_price = D(current_price)
        self.shares = D(shares_outstanding)
        self.net_debt = D(net_debt)
        self.fcf_ttm = D(fcf_ttm) if fcf_ttm else None
        self.revenue_ttm = D(revenue_ttm) if revenue_ttm else None
        self.ebit_ttm = D(ebit_ttm) if ebit_ttm else None
        self.wacc = D(wacc)
        self.terminal_g = D(terminal_growth_rate)
        self.tax_rate = D(tax_rate)
        self.n_years = forecast_years

        # 衍生值
        self.market_cap = self.current_price * self.shares
        self.ev = self.market_cap + self.net_debt

    def solve_implied_growth(self) -> ReverseDCFResult:
        """单变量求解: 给定 EV/WACC/FCF, 解隐含永续增长率 g

        使用 Newton-Raphson 迭代:
        EV = FCF_ttm × Σ(1+g)^i/(1+WACC)^i + FCF_ttm×(1+g)^n / (WACC-g) / (1+WACC)^n
        """
        result = ReverseDCFResult()
        result.market_cap = dto_float(self.market_cap)
        result.enterprise_value = dto_float(self.ev)

        if self.fcf_ttm is None or self.fcf_ttm <= 0:
            result.warnings.append("缺少 FCF_ttm，无法求解隐含增长率")
            result.converged = False
            return result

        fcf = self.fcf_ttm
        ev = self.ev
        wacc = self.wacc
        n = self.n_years

        # Newton-Raphson: find g such that DCF(g) = EV
        def dcf_value(g: D) -> D:
            if wacc <= g:
                return D("999999")
            # 预测期 PV of FCF
            sum_pv = D(0)
            for i in range(n):
                fcf_i = fcf * (D(1) + g) ** (i + 1)
                df = D(1) / ((D(1) + wacc) ** (i + 1))
                sum_pv += fcf_i * df
            # 终值
            tv_fcf = fcf * (D(1) + g) ** n * (D(1) + g)
            tv = tv_fcf / (wacc - g)
            tv_pv = tv / ((D(1) + wacc) ** n)
            return sum_pv + tv_pv

        # 迭代求解
        g = D(0.03)  # 初始猜测
        hit_upper = False
        hit_lower = False
        for i in range(100):
            fv = dcf_value(g)
            residual = fv - ev
            if abs(residual) < D("0.001"):
                break
            # 数值导数
            dg = D("0.0001")
            f_plus = dcf_value(g + dg)
            derivative = (f_plus - fv) / dg
            if abs(derivative) < D("1e-10"):
                break
            g = g - residual / derivative
            # 边界约束
            if g < D(-0.05):
                g = D(-0.05)
                hit_lower = True
            if g > D(0.15):
                g = D(0.15)
                hit_upper = True
            if hit_upper or hit_lower:
                break

        result.implied_growth_rate = dto_float(g)
        result.ev_to_fcf = dto_float(ev / fcf)
        result.iterations = 100
        result.residual = dto_float(abs(dcf_value(g) - ev))
        result.converged = result.residual < 1.0

        if hit_upper:
            result.warnings.append(f"增长率触及上限15%，隐含EV/FCF={result.ev_to_fcf:.1f}x（市场预期极高）")
        elif hit_lower:
            result.warnings.append(f"增长率触及下限-5%，隐含EV/FCF={result.ev_to_fcf:.1f}x（市场预期极低）")

        # 分解: growth / value / quality 贡献
        self._decompose_contributions(result, g, fcf)

        return result

    def solve_implied_margin_and_growth(self) -> ReverseDCFResult:
        """双变量求解: 同时解 (FCF margin, growth)

        系统:
        EV = FCF × PV_factor(g, WACC)
        FCF = revenue_ttm × margin × (1+g)^n
        """
        result = self.solve_implied_growth()

        if self.revenue_ttm and self.revenue_ttm > 0 and self.fcf_ttm and self.fcf_ttm > 0:
            margin = self.fcf_ttm / self.revenue_ttm
            result.implied_fcf_margin = dto_float(margin)

        return result

    def expectation_gap_analysis(self, our_growth: float, our_margin: Optional[float] = None) -> ReverseDCFResult:
        """期望差距分析: 我们的假设 vs 市场隐含"""
        implied = self.solve_implied_growth()

        our_g = D(our_growth)
        implied_g = D(implied.implied_growth_rate)

        result = ReverseDCFResult(
            implied_growth_rate=implied.implied_growth_rate,
            enterprise_value=implied.enterprise_value,
            ev_to_fcf=implied.ev_to_fcf,
            converged=implied.converged,
            our_growth=our_growth,
            implied_growth=implied.implied_growth_rate,
            expectation_gap_pp=dto_float((our_g - implied_g) * D(100)),
            growth_contribution_pct=implied.growth_contribution_pct,
            value_contribution_pct=implied.value_contribution_pct,
            quality_contribution_pct=implied.quality_contribution_pct,
        )

        # 价格跌到公允价值时的跌幅
        if self.fcf_ttm and self.fcf_ttm > 0:
            fair_ev = self.fcf_ttm * (D(1) + our_g) / (self.wacc - our_g)
            fair_equity = fair_ev - self.net_debt
            fair_price = fair_equity / self.shares
            result.price_drop_to_fair_value_pct = dto_float((fair_price / self.current_price - D(1)) * D(100))

        return result

    def _decompose_contributions(self, result: ReverseDCFResult, implied_g: D, fcf: D) -> None:
        """分解 EV 的增长/价值/质量贡献"""
        wacc = self.wacc
        n = self.n_years

        # 无增长时的 EPV
        if wacc > 0:
            epv = fcf / wacc
        else:
            epv = fcf * D(100)

        # 增长部分的 PV
        growth_pv = D(0)
        for i in range(n):
            fcf_i = fcf * (D(1) + implied_g) ** (i + 1)
            df = D(1) / ((D(1) + wacc) ** (i + 1))
            growth_pv += fcf_i * df
        growth_pv -= epv * D(n) / D(n + 1)  # 近似

        total = D(result.enterprise_value) if result.enterprise_value > 0 else D(1)

        result.value_contribution_pct = dto_float(epv / total * D(100)) if total > 0 else 0
        result.growth_contribution_pct = dto_float(growth_pv / total * D(100)) if total > 0 else 0
        result.quality_contribution_pct = max(0, 100 - result.value_contribution_pct - result.growth_contribution_pct)
