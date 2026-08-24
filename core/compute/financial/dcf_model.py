"""V51.6 DCF 估值模型升级版 — 对标130家投行估值模型标准

升级点：
  1. WACC 逐项拆解透明化（Beta/无风险利率/ERP/资本结构 → 每一步可见）
  2. 双变量敏感性矩阵表格化输出（WACC × 永续增长率）
  3. 关键假设独立管理 → 支持单变量修改整表重算
  4. AssumptionTree 的自动填充

对标：130 家估值模型的共同标准
  美团模型：WACC=11.1%，Beta=1.35，无风险利率=3.0%，ERP=6.0%，资本结构=0%
  宁德时代模型：三张表联动，敏感性矩阵 4×5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from core.models import AssumptionNode, AssumptionTree

logger = logging.getLogger("v51.valuation.dcf")


@dataclass
class DCFResult:
    """DCF 估值结果（升级版）。"""

    company: str = ""
    stock_code: str = ""
    present_value_of_fcf: float = 0.0
    terminal_value: float = 0.0
    enterprise_value: float = 0.0
    net_debt: float = 0.0
    equity_value: float = 0.0
    target_price: float = 0.0
    shares_outstanding: float = 0.0

    # WACC 逐项拆解（新增 — 对标美团模型）
    wacc_breakdown: dict = field(
        default_factory=lambda: {
            "risk_free_rate": 0.0,
            "equity_risk_premium": 0.0,
            "beta": 0.0,
            "cost_of_equity": 0.0,
            "cost_of_debt": 0.0,
            "debt_ratio": 0.0,
            "tax_rate": 0.0,
            "wacc": 0.0,
        }
    )

    # 假设树引用
    assumptions: AssumptionTree | None = None

    # 敏感性矩阵（WACC × 永续增长率）
    sensitivity_wacc_range: list[float] = field(default_factory=list)
    sensitivity_g_range: list[float] = field(default_factory=list)
    sensitivity_matrix: list[list[float]] = field(default_factory=list)

    # 其他
    confidence: str = "medium"
    details: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def format_sensitivity_table(self) -> str:
        """输出敏感性矩阵为 markdown 表格。

        格式对标美团模型的 DCF 估值结果表：

        | WACC \\ g | 1.5% | 2.0% | 2.5% | 3.0% |
        |----------|------|------|------|------|
        | 9%       | 45.4 | 48.2 | ---  | ---  |
        | 11%      | 32.1 | 33.2 | 34.4 | ---  |
        | 13%      | 24.2 | 24.8 | 25.4 | 26.1 |
        | 15%      | 19.7 | 20.1 | 20.4 | 20.8 |
        """
        if not self.sensitivity_matrix:
            return "（敏感性数据不足）"
        lines = []
        header = ["WACC \\ g"] + [f"{g * 100:.1f}%" for g in self.sensitivity_g_range]
        lines.append("| " + " | ".join(f"{h:>8}" for h in header) + " |")
        lines.append("|" + "|".join([":------:"] * len(header)) + "|")
        for i, wacc in enumerate(self.sensitivity_wacc_range):
            row = [f"{wacc * 100:.0f}%"]
            for j in range(len(self.sensitivity_g_range)):
                val = (
                    self.sensitivity_matrix[i][j]
                    if i < len(self.sensitivity_matrix) and j < len(self.sensitivity_matrix[i])
                    else 0
                )
                if val > 0:
                    row.append(f"{val:.1f}")
                else:
                    row.append("—")
            lines.append("| " + " | ".join(f"{c:>8}" for c in row) + " |")
        return "\n".join(lines)

    def format_wacc_breakdown(self) -> str:
        """输出 WACC 拆解为 markdown 表格。"""
        wb = self.wacc_breakdown
        lines = []
        lines.append("| 参数 | 值 | 说明 |")
        lines.append("|------|-----|------|")
        lines.append(f"| 无风险利率 | {wb.get('risk_free_rate', 0) * 100:.1f}% | 通常取10年期国债收益率 |")
        lines.append(f"| 股权风险溢价 | {wb.get('equity_risk_premium', 0) * 100:.1f}% | 市场风险溢价 |")
        lines.append(f"| Beta | {wb.get('beta', 0):.2f}x | 与可比公司对标 |")
        lines.append(f"| 股权成本 | {wb.get('cost_of_equity', 0) * 100:.1f}% | = Rf + β × ERP |")
        lines.append(f"| 债务成本 | {wb.get('cost_of_debt', 0) * 100:.1f}% | 税后 |")
        lines.append(f"| 目标资本结构 | {wb.get('debt_ratio', 0) * 100:.0f}% | 负债/总资本 |")
        lines.append(f"| WACC | {wb.get('wacc', 0) * 100:.1f}% | 加权平均 |")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 计算引擎
# ═══════════════════════════════════════════════════════════════


def compute_dcf(
    revenue_projections: list[float] = None,
    ebit_margin_projections: list[float] = None,
    tax_rate: float = 0.25,
    da_pct_of_revenue: float = 0.05,
    capex_pct_of_revenue: float = 0.06,
    working_capital_pct: float = 0.05,
    wacc_assumptions: dict = None,
    terminal_growth: float = 0.025,
    exit_multiple: float = None,
    net_debt: float = 0.0,
    shares_outstanding: float = 1.0,
    projection_years: int = 10,
    company: str = "",
    stock_code: str = "",
) -> DCFResult:
    """DCF 估值计算（升级版 —— WACC 拆解 + 敏感性矩阵）。

    输入参数全部以假设树形式独立管理，
    支持单变量修改整表重算。

    Args:
        revenue_projections: 预测期各年营收（亿元）
        ebit_margin_projections: 预测期各年 EBIT 利润率
        wacc_assumptions: WACC 拆解参数
            {"risk_free_rate": 0.03, "equity_risk_premium": 0.06, "beta": 1.35,
             "cost_of_debt": 0.03, "debt_ratio": 0.0, "tax_rate": 0.25}
    """
    result = DCFResult(company=company, stock_code=stock_code)

    # 1. WACC 拆解
    wa = wacc_assumptions or {}
    rfr = wa.get("risk_free_rate", 0.03)
    erp = wa.get("equity_risk_premium", 0.06)
    beta = wa.get("beta", 1.0)
    coe = rfr + beta * erp
    cod = wa.get("cost_of_debt", 0.03)
    dr = wa.get("debt_ratio", 0.0)
    tr = tax_rate
    wacc = coe * (1 - dr) + cod * dr * (1 - tr)

    result.wacc_breakdown = {
        "risk_free_rate": rfr,
        "equity_risk_premium": erp,
        "beta": beta,
        "cost_of_equity": coe,
        "cost_of_debt": cod,
        "debt_ratio": dr,
        "tax_rate": tr,
        "wacc": wacc,
    }

    if revenue_projections is None or len(revenue_projections) < 2:
        result.warnings.append("营收预测数据不足，无法计算 DCF")
        return result

    n = min(len(revenue_projections), projection_years)
    fcf_list = []
    for i in range(n):
        rev = revenue_projections[i]
        ebit = rev * (
            ebit_margin_projections[i] if ebit_margin_projections and i < len(ebit_margin_projections) else 0.15
        )
        nopat = ebit * (1 - tax_rate)
        da = rev * da_pct_of_revenue
        capex = rev * capex_pct_of_revenue
        delta_wc = rev * working_capital_pct * (0.15 if i == 0 else 0.10)  # 首年高
        fcf = nopat + da - capex - delta_wc
        fcf_list.append(fcf)

    # 2. 折现
    pv_fcf = sum(fcf / (1 + wacc) ** (i + 1) for i, fcf in enumerate(fcf_list))

    # 3. 终值
    last_fcf = fcf_list[-1]
    if terminal_growth < wacc:
        tv = last_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    else:
        tv = 0.0
        result.warnings.append(
            f"永续增长率 {terminal_growth * 100:.1f}% 大于 WACC {wacc * 100:.1f}%，终值使用 Exit Multiple"
        )
        if exit_multiple:
            last_ebitda = revenue_projections[-1] * 0.25  # 假设 EBITDA 利润率 25%
            tv = last_ebitda * exit_multiple

    pv_tv = tv / (1 + wacc) ** n
    ev = pv_fcf + pv_tv
    eq = ev - net_debt
    target_price = eq / shares_outstanding if shares_outstanding > 0 else 0

    result.present_value_of_fcf = round(pv_fcf, 2)
    result.terminal_value = round(pv_tv, 2)
    result.enterprise_value = round(ev, 2)
    result.net_debt = round(net_debt, 2)
    result.equity_value = round(eq, 2)
    result.target_price = round(target_price, 2)
    result.shares_outstanding = shares_outstanding

    # 4. 敏感性矩阵（WACC × g）
    wacc_range = [wacc - 0.02, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.02]
    g_range = [max(0.005, terminal_growth - 0.01), terminal_growth, terminal_growth + 0.01]
    matrix = []
    for w in wacc_range:
        row = []
        for g in g_range:
            if g < w:
                tv_g = last_fcf * (1 + g) / (w - g)
                pv_tv_g = tv_g / (1 + w) ** n
                ev_g = pv_fcf + pv_tv_g
                eq_g = ev_g - net_debt
                tp_g = eq_g / shares_outstanding if shares_outstanding > 0 else 0
                row.append(round(tp_g, 1))
            else:
                row.append(0.0)
        matrix.append(row)

    result.sensitivity_wacc_range = [round(w, 4) for w in wacc_range]
    result.sensitivity_g_range = [round(g, 4) for g in g_range]
    result.sensitivity_matrix = matrix

    return result


def build_assumption_tree(
    revenue_projections: list[float],
    ebit_margin_projections: list[float],
    wacc_assumptions: dict,
    terminal_growth: float,
    company_name: str = "",
) -> AssumptionTree:
    """从 DCF 输入参数自动构建假设树。"""
    tree = AssumptionTree()

    # 利润层
    tree.margin_assumptions = {
        "ebit_margin": ebit_margin_projections[-1] if ebit_margin_projections else 0.15,
        "tax_rate": wacc_assumptions.get("tax_rate", 0.25),
    }

    # 资本层
    tree.wacc_assumptions = {
        "risk_free_rate": wacc_assumptions.get("risk_free_rate", 0.03),
        "equity_risk_premium": wacc_assumptions.get("equity_risk_premium", 0.06),
        "beta": wacc_assumptions.get("beta", 1.0),
        "cost_of_equity": wacc_assumptions.get("risk_free_rate", 0.03)
        + wacc_assumptions.get("beta", 1.0) * wacc_assumptions.get("equity_risk_premium", 0.06),
        "cost_of_debt": wacc_assumptions.get("cost_of_debt", 0.03),
        "debt_ratio": wacc_assumptions.get("debt_ratio", 0.0),
        "wacc": 0.0,  # 由 compute_dcf 填充
    }

    # 终值层
    tree.terminal_growth = terminal_growth

    # 营收驱动
    for i, rev in enumerate(revenue_projections):
        node = AssumptionNode(
            name=f"营收_{'预测' if i > 0 else '基准'}",
            value=rev,
            unit="亿元",
            is_historical=(i == 0),
        )
        if i > 0:
            prev = revenue_projections[i - 1]
            node.growth_rate = (rev / prev - 1) if prev > 0 else None
        tree.revenue_drivers.append(node)

    return tree
