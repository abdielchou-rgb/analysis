"""
1号分析师 V30 — DCF 估值模型

基于麦肯锡估值第8版方法论，计算：
  1. 预测期自由现金流 (FCF) 现值
  2. 终值（Gordon Growth Model 或 Exit Multiple）
  3. 加权平均资本成本 (WACC) via CAPM
  4. 双变量敏感性矩阵 (WACC × 终值增长率)

核心公式:
  FCF = NOPAT + D&A - CapEx - ΔWorkingCapital
  NOPAT = EBIT × (1 - TaxRate)
  WACC = E/(E+D) × Re + D/(E+D) × Rd × (1-Tax)
  Enterprise Value = Σ(FCFt / (1+WACC)^t) + TerminalValue / (1+WACC)^n
  Terminal Value (GGM) = FCFn × (1+g) / (WACC - g)
  Terminal Value (Exit) = EBITDA_n × ExitMultiple
  Equity Value = EV - Net Debt + Excess Cash
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from core.models import ComputedResults, StructuredData

logger = logging.getLogger("v30.valuation.dcf")


@dataclass
class DCFResult:
    """DCF 估值结果。"""
    company: str
    stock_code: str
    present_value_of_fcf: float       # 预测期 FCF 现值总和（亿元）
    terminal_value: float              # 终值（亿元）
    enterprise_value: float            # 企业价值 = PV(FCF) + PV(终值)（亿元）
    equity_value: float                # 股权价值 = EV - 净债务 + 超额现金（亿元）
    target_price: float                # 目标价 = 股权价值 / 总股本（元/股）
    assumptions: dict = field(default_factory=dict)
    sensitivity_matrix: dict = field(default_factory=dict)
    confidence: str = "medium"
    details: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def compute_dcf(
    l1_data: Optional[StructuredData] = None,
    results: Optional[ComputedResults] = None,
    # ── 核心假设参数 ──
    projection_years: int = 5,
    terminal_growth_rate: float = 0.03,
    wacc: Optional[float] = None,
    # CAPM 参数
    risk_free_rate: float = 0.028,
    beta: float = 1.0,
    equity_risk_premium: float = 0.065,
    cost_of_debt: float = 0.045,
    debt_ratio: float = 0.20,
    tax_rate: float = 0.25,
    # 终值方法
    terminal_method: str = "ggm",
    exit_ebitda_multiple: float = 10.0,
    # 营收增长率预测
    revenue_growth_rates: Optional[list[float]] = None,
    target_operating_margin: Optional[float] = None,
    target_da_pct_revenue: float = 0.03,
    target_capex_pct_revenue: float = 0.04,
    target_wc_pct_revenue: float = 0.02,
) -> Optional[DCFResult]:
    """
    执行 DCF 估值计算。

    Args:
        l1_data: L1 层结构化数据
        results: L2 已有计算结果
        projection_years: 预测期年数
        terminal_growth_rate: 终值增长率
        wacc: 若指定则直接使用，否则通过 CAPM 计算
        risk_free_rate: 无风险利率（10年国债，默认2.8%）
        beta: beta 系数
        equity_risk_premium: 股权风险溢价（默认6.5%）
        cost_of_debt: 债务成本
        debt_ratio: 债务占比 D/(D+E)
        tax_rate: 企业所得税率
        terminal_method: "ggm" 或 "exit_multiple"
        exit_ebitda_multiple: 退出倍数
        revenue_growth_rates: 预测期逐年的营收增速列表
        target_operating_margin: 目标营业利润率
        target_da_pct_revenue: D&A 占营收比
        target_capex_pct_revenue: CapEx 占营收比
        target_wc_pct_revenue: 营运资本变动占营收比

    Returns:
        DCFResult 或 None（数据不足时）
    """
    company = ""
    stock_code = ""
    if results is not None:
        company = results.company
        stock_code = results.stock_code
    elif l1_data is not None:
        company = l1_data.profile.stock_name
        stock_code = l1_data.profile.stock_code

    # ── 1. 确定基准营收和利润率 ──
    latest_revenue = None
    latest_ebit_margin = None
    latest_total_shares = None
    latest_net_debt = 0.0
    latest_ebitda_margin = None

    if results is not None and results.financial_summary:
        fs = results.financial_summary
        latest_year = max(fs.years) if fs.years else None
        if latest_year:
            rev = fs.items.get("营收(亿元)", {}).get(str(latest_year))
            if rev is not None:
                latest_revenue = float(rev)

    if l1_data is not None:
        financials = sorted(l1_data.financials, key=lambda x: x.fiscal_year)
        if financials:
            last = financials[-1]
            if latest_revenue is None:
                latest_revenue = last.revenue
            if last.ebit_margin is not None:
                latest_ebit_margin = last.ebit_margin
            if last.total_shares is not None:
                latest_total_shares = last.total_shares
            if last.ebit_margin is not None:
                latest_ebitda_margin = last.ebit_margin + target_da_pct_revenue * 100

    if latest_revenue is None or latest_revenue <= 0:
        logger.warning("[DCF] 基准营收数据不足，无法计算")
        return None

    warnings = []

    # ── 2. 计算 WACC ──
    if wacc is None:
        re = risk_free_rate + beta * equity_risk_premium
        rd_after_tax = cost_of_debt * (1 - tax_rate)
        equity_ratio = 1.0 - debt_ratio
        wacc = equity_ratio * re + debt_ratio * rd_after_tax
        logger.info(f"[DCF] WACC 计算: Re={re:.2%}, Rd(at)={rd_after_tax:.2%}, "
                     f"WACC={wacc:.2%}")

    # ── 3. 构建 FCF 预测 ──
    if revenue_growth_rates is None:
        historical_growth = _estimate_historical_growth(l1_data)
        if historical_growth is not None:
            base_growth = max(historical_growth, 0.02)
        else:
            base_growth = 0.08
        revenue_growth_rates = []
        for i in range(projection_years):
            t = (i + 1) / projection_years
            rate = base_growth * (1 - t) + (terminal_growth_rate + 0.01) * t
            revenue_growth_rates.append(round(rate, 4))

    if target_operating_margin is None:
        if latest_ebit_margin is not None:
            target_operating_margin = latest_ebit_margin / 100.0
        else:
            target_operating_margin = 0.15

    # 逐年 FCF
    fcf_projections: list[dict] = []
    current_revenue = latest_revenue

    for i in range(projection_years):
        growth = revenue_growth_rates[i]
        year_num = i + 1

        revenue = round(current_revenue * (1 + growth), 4)
        ebit = round(revenue * target_operating_margin, 4)
        nopat = round(ebit * (1 - tax_rate), 4)
        da = round(revenue * target_da_pct_revenue, 4)
        capex = round(revenue * target_capex_pct_revenue, 4)
        wc_change = round(revenue * target_wc_pct_revenue, 4)
        fcf = round(nopat + da - capex - wc_change, 4)

        discount_factor = round(1 / ((1 + wacc) ** year_num), 6)
        pv_fcf = round(fcf * discount_factor, 4)

        fcf_projections.append({
            "year": year_num,
            "revenue": revenue,
            "growth": round(growth * 100, 2),
            "ebit_margin": round(target_operating_margin * 100, 2),
            "ebit": ebit,
            "nopat": nopat,
            "da": da,
            "capex": capex,
            "wc_change": wc_change,
            "fcf": fcf,
            "discount_factor": discount_factor,
            "pv_fcf": pv_fcf,
        })
        current_revenue = revenue

    present_value_of_fcf = round(sum(p["pv_fcf"] for p in fcf_projections), 4)

    # ── 4. 终值计算 ──
    terminal_fcf = fcf_projections[-1]["fcf"]
    terminal_ebitda = round(
        fcf_projections[-1]["revenue"]
        * (latest_ebitda_margin or 15.0) / 100,
        4,
    )

    if terminal_method == "ggm":
        if wacc <= terminal_growth_rate:
            logger.warning(f"[DCF] WACC <= 终值增长率，切换为退出倍数法")
            terminal_method = "exit_multiple"
            terminal_value = round(terminal_ebitda * exit_ebitda_multiple, 4)
            warnings.append("WACC <= 终值增长率，强制切换为退出倍数法")
        else:
            terminal_value = round(
                terminal_fcf * (1 + terminal_growth_rate) / (wacc - terminal_growth_rate), 4
            )
    else:
        terminal_value = round(terminal_ebitda * exit_ebitda_multiple, 4)

    pv_terminal = round(terminal_value / ((1 + wacc) ** projection_years), 4)

    # ── 5. 企业价值与股权价值 ──
    enterprise_value = round(present_value_of_fcf + pv_terminal, 4)

    if latest_total_shares is None:
        latest_total_shares = 1_000_000_000
        warnings.append("总股本数据缺失，使用默认值10亿股")

    equity_value = round(enterprise_value - latest_net_debt, 4)

    shares_yi = latest_total_shares / 1e8  # 转换为亿股
    target_price = round(equity_value / shares_yi if shares_yi > 0 else 0, 2)

    # ── 6. 敏感性矩阵 ──
    sensitivity_matrix = _build_sensitivity_matrix(
        fcf_projections=fcf_projections,
        terminal_fcf=terminal_fcf,
        terminal_ebitda=terminal_ebitda,
        base_wacc=wacc,
        base_terminal_growth=terminal_growth_rate,
        projection_years=projection_years,
        terminal_method=terminal_method,
        exit_ebitda_multiple=exit_ebitda_multiple,
        latest_net_debt=latest_net_debt,
        latest_total_shares=latest_total_shares,
    )

    # ── 7. 置信度评估 ──
    confidence = _assess_confidence(terminal_value, enterprise_value, warnings)

    result = DCFResult(
        company=company,
        stock_code=stock_code,
        present_value_of_fcf=present_value_of_fcf,
        terminal_value=terminal_value,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        target_price=target_price,
        assumptions={
            "wacc": round(wacc, 6),
            "risk_free_rate": risk_free_rate,
            "beta": beta,
            "equity_risk_premium": equity_risk_premium,
            "cost_of_debt": cost_of_debt,
            "debt_ratio": debt_ratio,
            "tax_rate": tax_rate,
            "terminal_growth_rate": terminal_growth_rate,
            "terminal_method": terminal_method,
            "exit_ebitda_multiple": exit_ebitda_multiple,
            "projection_years": projection_years,
            "revenue_growth_rates": revenue_growth_rates,
            "target_operating_margin": round(target_operating_margin, 4),
            "revenue_base": latest_revenue,
            "total_shares": latest_total_shares,
            "net_debt": latest_net_debt,
        },
        sensitivity_matrix=sensitivity_matrix,
        confidence=confidence,
        details={
            "fcf_projections": fcf_projections,
            "pv_terminal": pv_terminal,
            "terminal_fcf": terminal_fcf,
            "terminal_ebitda": terminal_ebitda,
        },
        warnings=warnings,
    )

    return result


# ═══════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════


def _estimate_historical_growth(l1_data: Optional[StructuredData]) -> Optional[float]:
    """基于历史营收数据估算 CAGR。"""
    if l1_data is None:
        return None
    financials = sorted(l1_data.financials, key=lambda x: x.fiscal_year)
    if len(financials) < 2:
        return None
    first = financials[0]
    last = financials[-1]
    if first.revenue and last.revenue and first.revenue > 0 and last.revenue > 0:
        n = len(financials) - 1
        return (last.revenue / first.revenue) ** (1 / n) - 1
    return None


def _build_sensitivity_matrix(
    fcf_projections: list[dict],
    terminal_fcf: float,
    terminal_ebitda: float,
    base_wacc: float,
    base_terminal_growth: float,
    projection_years: int,
    terminal_method: str,
    exit_ebitda_multiple: float,
    latest_net_debt: float,
    latest_total_shares: int,
) -> dict:
    """
    双变量敏感性矩阵。

    X 轴: WACC（-0.5pp ~ +0.5pp，步长 0.25pp）
    Y 轴: 终值增长率（-0.5pp ~ +0.5pp，步长 0.25pp）
    输出: {"wacc_pct": {"growth_pct": target_price}}
    """
    wacc_range = [base_wacc + i * 0.0025 for i in range(-2, 3)]
    growth_range = [base_terminal_growth + i * 0.0025 for i in range(-2, 3)]
    base_fcf_values = [p["fcf"] for p in fcf_projections]

    matrix = {}
    for w in wacc_range:
        row = {}
        pv_fcf_sum = sum(
            base_fcf_values[t] / ((1 + w) ** (t + 1))
            for t in range(len(base_fcf_values))
        )
        for g in growth_range:
            if terminal_method == "ggm" and w > g:
                tv = terminal_fcf * (1 + g) / (w - g)
            elif terminal_method == "exit_multiple":
                tv = terminal_ebitda * exit_ebitda_multiple
            else:
                tv = 0
            pv_tv = tv / ((1 + w) ** projection_years)
            ev = round(pv_fcf_sum + pv_tv, 4)
            eqv = round(ev - latest_net_debt, 4)
            tp = round(eqv / (latest_total_shares / 1e8), 2) if latest_total_shares else 0
            row[round(g * 100, 2)] = tp

        matrix[round(w * 100, 2)] = row

    return matrix


def _assess_confidence(
    terminal_value: float, enterprise_value: float, warnings: list[str]
) -> str:
    """评估 DCF 置信度。"""
    if enterprise_value <= 0:
        return "low"
    terminal_ratio = abs(terminal_value) / abs(enterprise_value) if enterprise_value else 1
    if terminal_ratio > 0.8:
        return "low"
    if terminal_ratio > 0.6:
        return "medium"
    if len(warnings) > 3:
        return "low"
    return "high"


def format_dcf_for_report(dcf: DCFResult) -> str:
    """将 DCF 格式化为报告文本块。"""
    lines = []
    lines.append(f"## DCF 估值模型: {dcf.company}")
    lines.append("")

    a = dcf.assumptions
    details = dcf.details

    # 核心结果
    lines.append("### 估值结果")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 预测期FCF现值 | {dcf.present_value_of_fcf:.2f} 亿元 |")
    lines.append(f"| 终值 | {dcf.terminal_value:.2f} 亿元 |")
    lines.append(f"| 企业价值 (EV) | {dcf.enterprise_value:.2f} 亿元 |")
    lines.append(f"| 股权价值 | {dcf.equity_value:.2f} 亿元 |")
    lines.append(f"| 目标价 | {dcf.target_price:.2f} 元 |")
    lines.append(f"| 置信度 | {dcf.confidence} |")
    lines.append("")

    # 假设
    lines.append("### 核心假设")
    lines.append("")
    lines.append("| 参数 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| WACC | {a.get('wacc', 0) * 100:.2f}% |")
    lines.append(f"| 无风险利率 | {a.get('risk_free_rate', 0) * 100:.2f}% |")
    lines.append(f"| Beta | {a.get('beta', 1.0):.2f} |")
    lines.append(f"| 股权风险溢价 | {a.get('equity_risk_premium', 0) * 100:.2f}% |")
    lines.append(f"| 终值增长率 | {a.get('terminal_growth_rate', 0) * 100:.2f}% |")
    lines.append(f"| 预测期 | {a.get('projection_years', 5)} 年 |")
    lines.append(f"| 终值方法 | {a.get('terminal_method', 'ggm')} |")
    lines.append(f"| 目标营业利润率 | {a.get('target_operating_margin', 0) * 100:.2f}% |")
    lines.append(f"| 基准营收 | {a.get('revenue_base', 0):.2f} 亿元 |")
    lines.append("")

    # FCF 预测明细
    lines.append("### FCF 预测明细")
    lines.append("")
    header = "| 年份 | 营收(亿) | 增速% | EBIT利润率% | NOPAT(亿) | D&A(亿) | CapEx(亿) | WC变动(亿) | FCF(亿) | 折现因子 | PV(FCF)(亿) |"
    sep = "|------|---------|-------|------------|----------|--------|----------|-----------|--------|---------|-----------|"
    lines.append(header)
    lines.append(sep)
    for p in details.get("fcf_projections", []):
        lines.append(
            f"| {p['year']} | {p['revenue']:.2f} | {p['growth']:.1f}% | "
            f"{p['ebit_margin']:.1f}% | {p['nopat']:.2f} | {p['da']:.2f} | "
            f"{p['capex']:.2f} | {p['wc_change']:.2f} | {p['fcf']:.2f} | "
            f"{p['discount_factor']:.4f} | {p['pv_fcf']:.2f} |"
        )
    lines.append("")

    # 终值
    lines.append("### 终值计算")
    lines.append("")
    lines.append(f"- 方法: {a.get('terminal_method', 'ggm')}")
    lines.append(f"- 终值FCF: {details.get('terminal_fcf', 0):.2f} 亿元")
    lines.append(f"- 终值: {dcf.terminal_value:.2f} 亿元")
    lines.append(f"- PV(终值): {details.get('pv_terminal', 0):.2f} 亿元")
    tv_ratio = dcf.terminal_value / dcf.enterprise_value * 100 if dcf.enterprise_value else 0
    lines.append(f"- 终值占EV比: {tv_ratio:.1f}%")
    lines.append("")

    # 警告
    if dcf.warnings:
        lines.append("### 警告")
        for w in dcf.warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)
