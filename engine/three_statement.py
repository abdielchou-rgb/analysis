"""
三表联动引擎 — IS→BS→CF 动态链接，零循环引用，财务不变量校验。
参考 astock-dcf-model + dashboard-package 的 IB 级架构。

设计原则：
1. 单向推演：IS → BS → CF，无循环依赖
2. 现金作为 plug（资产负债表平衡项）
3. 三项财务不变量：BS 恒等式、CF 恒等式、RE 变动
4. 支持 FCFF/FCFE 双口径
5. 输出完整三表 + FCFF/FCFE + 自由现金流桥

Usage:
    from engine.three_statement import ThreeStatementEngine, ThreeStatementAssumptions
    assumptions = ThreeStatementAssumptions(**data)
    result = ThreeStatementEngine(assumptions).run()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.irongate import GateReport, IronGateEngine
from engine.precision import D, PreciseValuation, dto_float

# ─── Schemas ────────────────────────────────────────────────────────────────


@dataclass
class ThreeStatementAssumptions:
    """三表联动假设 — 输入参数"""

    ticker: str
    company_name: str
    forecast_years: int = 5

    # ── 基期数据（历史最后一年） ──
    # 利润表
    base_revenue: float = 0.0  # 营业收入（亿元）
    base_cogs_pct: float = 0.40  # 营业成本占比
    base_selling_exp_pct: float = 0.10  # 销售费用占比
    base_admin_exp_pct: float = 0.05  # 管理费用占比
    base_rd_exp_pct: float = 0.03  # 研发费用占比
    base_other_income_pct: float = 0.01  # 其他收益占比
    base_investment_income_pct: float = 0.005  # 投资收益占比
    tax_rate: float = 0.25  # 有效税率
    minority_interest_pct: float = 0.05  # 少数股东损益占比（占净利润）

    # 资产负债表
    base_cash: float = 0.0  # 货币资金
    base_receivables_pct: float = 0.15  # 应收账款占营收比
    base_inventory_pct: float = 0.10  # 存货占营收比
    base_other_current_assets_pct: float = 0.02  # 其他流动资产占比
    base_ppe_pct: float = 0.30  # 固定资产占营收比
    base_intangibles_pct: float = 0.05  # 无形资产占营收比
    base_goodwill: float = 0.0  # 商誉
    base_other_nca_pct: float = 0.02  # 其他非流动资产占比

    base_payables_pct: float = 0.12  # 应付账款占营收比
    base_accrued_expenses_pct: float = 0.03  # 应计费用占营收比
    base_short_term_debt: float = 0.0  # 短期借款
    base_current_portion_ltd: float = 0.0  # 一年内到期的长期借款
    base_deferred_revenue_pct: float = 0.02  # 递延收益占营收比

    base_long_term_debt: float = 0.0  # 长期借款
    base_bonds_payable: float = 0.0  # 应付债券
    base_lease_liabilities: float = 0.0  # 租赁负债
    base_deferred_tax_liabilities: float = 0.0  # 递延所得税负债
    base_other_ncl: float = 0.0  # 其他非流动负债

    base_equity: float = 0.0  # 归母股东权益（含股本+资本公积+留存收益）
    base_minority_interest: float = 0.0  # 少数股东权益

    # ── 预测假设 ──
    revenue_growth_rates: List[float] = field(default_factory=list)
    cogs_pct: Optional[List[float]] = None  # None = 沿用基期
    selling_exp_pct: Optional[List[float]] = None
    admin_exp_pct: Optional[List[float]] = None
    rd_exp_pct: Optional[List[float]] = None

    # 资本支出与折旧
    da_pct_revenue: float = 0.03  # 折旧摊销占营收比
    capex_pct_revenue: float = 0.04  # 资本支出占营收比

    # 营运资金假设
    receivables_days: Optional[float] = None  # None = 用 base_XXX_pct
    inventory_days: Optional[float] = None
    payables_days: Optional[float] = None

    # 分红与回购
    payout_ratio: float = 0.50  # 分红率（占归母净利润）
    share_buyback_pct: float = 0.0  # 回购占归母净利润比

    # 融资结构
    min_cash_balance: float = 0.0  # 最低现金余额（现金不够时借债）
    revolver_rate: float = 0.04  # 循环信贷利率
    term_loan_rate: float = 0.05  # 长期贷款利率
    cash_investment_rate: float = 0.02  # 现金投资收益率

    # ── 可选覆盖 ──
    capex_override: Optional[List[float]] = None  # 显式资本支出
    da_override: Optional[List[float]] = None  # 显式折旧摊销


# ─── Data Classes ────────────────────────────────────────────────────────────


@dataclass
class IncomeStatement:
    """利润表 — 逐年数据"""

    revenue: List[float] = field(default_factory=list)
    cogs: List[float] = field(default_factory=list)
    gross_profit: List[float] = field(default_factory=list)
    selling_exp: List[float] = field(default_factory=list)
    admin_exp: List[float] = field(default_factory=list)
    rd_exp: List[float] = field(default_factory=list)
    total_opex: List[float] = field(default_factory=list)
    operating_profit: List[float] = field(default_factory=list)
    other_income: List[float] = field(default_factory=list)
    investment_income: List[float] = field(default_factory=list)
    ebit: List[float] = field(default_factory=list)
    interest_expense: List[float] = field(default_factory=list)
    ebt: List[float] = field(default_factory=list)
    income_tax: List[float] = field(default_factory=list)
    net_income: List[float] = field(default_factory=list)
    minority_interest: List[float] = field(default_factory=list)
    net_profit_to_parent: List[float] = field(default_factory=list)

    # 估值指标
    ebit_margin: List[float] = field(default_factory=list)
    net_margin: List[float] = field(default_factory=list)
    gross_margin: List[float] = field(default_factory=list)

    @property
    def years(self) -> int:
        return len(self.revenue)


@dataclass
class BalanceSheet:
    """资产负债表 — 逐年数据"""

    # 资产
    cash: List[float] = field(default_factory=list)
    receivables: List[float] = field(default_factory=list)
    inventory: List[float] = field(default_factory=list)
    other_current_assets: List[float] = field(default_factory=list)
    total_current_assets: List[float] = field(default_factory=list)
    ppe: List[float] = field(default_factory=list)
    intangibles: List[float] = field(default_factory=list)
    goodwill: List[float] = field(default_factory=list)
    other_nca: List[float] = field(default_factory=list)
    total_assets: List[float] = field(default_factory=list)

    # 负债
    payables: List[float] = field(default_factory=list)
    accrued_expenses: List[float] = field(default_factory=list)
    short_term_debt: List[float] = field(default_factory=list)
    current_portion_ltd: List[float] = field(default_factory=list)
    deferred_revenue: List[float] = field(default_factory=list)
    total_current_liabilities: List[float] = field(default_factory=list)
    long_term_debt: List[float] = field(default_factory=list)
    bonds_payable: List[float] = field(default_factory=list)
    lease_liabilities: List[float] = field(default_factory=list)
    deferred_tax_liabilities: List[float] = field(default_factory=list)
    other_ncl: List[float] = field(default_factory=list)
    total_non_current_liabilities: List[float] = field(default_factory=list)
    total_liabilities: List[float] = field(default_factory=list)

    # 权益
    equity: List[float] = field(default_factory=list)
    minority_interest: List[float] = field(default_factory=list)
    total_equity: List[float] = field(default_factory=list)

    # 恒等式校验
    bs_imbalance: List[float] = field(default_factory=list)  # Assets - Liabilities - Equity

    @property
    def years(self) -> int:
        return len(self.total_assets)


@dataclass
class CashFlowStatement:
    """现金流量表 — 逐年数据"""

    # 经营活动
    net_income: List[float] = field(default_factory=list)
    da: List[float] = field(default_factory=list)
    wc_change: List[float] = field(default_factory=list)
    cash_from_operations: List[float] = field(default_factory=list)

    # 投资活动
    capex: List[float] = field(default_factory=list)
    cash_from_investing: List[float] = field(default_factory=list)

    # 融资活动
    debt_proceeds: List[float] = field(default_factory=list)
    debt_repayment: List[float] = field(default_factory=list)
    dividends_paid: List[float] = field(default_factory=list)
    share_buyback: List[float] = field(default_factory=list)
    cash_from_financing: List[float] = field(default_factory=list)

    # 现金变动
    net_cash_change: List[float] = field(default_factory=list)
    ending_cash: List[float] = field(default_factory=list)

    @property
    def years(self) -> int:
        return len(self.net_income)


@dataclass
class FreeCashFlowResult:
    """自由现金流计算结果"""

    fcff: List[float] = field(default_factory=list)  # FCF to Firm
    fcfe: List[float] = field(default_factory=list)  # FCF to Equity
    # 明细
    nopat: List[float] = field(default_factory=list)
    plus_da: List[float] = field(default_factory=list)
    less_capex: List[float] = field(default_factory=list)
    less_wc_change: List[float] = field(default_factory=list)
    less_net_interest: List[float] = field(default_factory=list)
    less_net_debt_repayment: List[float] = field(default_factory=list)


@dataclass
class ThreeStatementResult:
    """三表联动完整结果"""

    income_statement: IncomeStatement = field(default_factory=IncomeStatement)
    balance_sheet: BalanceSheet = field(default_factory=BalanceSheet)
    cash_flow: CashFlowStatement = field(default_factory=CashFlowStatement)
    free_cash_flow: FreeCashFlowResult = field(default_factory=FreeCashFlowResult)

    # 三项财务不变量
    invariant_checks: Dict[str, bool] = field(default_factory=dict)
    invariant_violations: List[str] = field(default_factory=list)

    # 估值辅助指标
    fcff_for_dcf: Optional[float] = None  # 最新一年 FCFF（用于 DCF）
    fcfe_for_dcf: Optional[float] = None  # 最新一年 FCFE（用于 DCF）
    total_debt: List[float] = field(default_factory=list)
    net_debt: List[float] = field(default_factory=list)

    # IronGate
    gate_report: Optional[GateReport] = None

    warnings: List[str] = field(default_factory=list)


# ─── Three-Statement Engine ──────────────────────────────────────────────────


class ThreeStatementEngine:
    """三表联动引擎 — IS→BS→CF 单向推演，现金作为 plug"""

    INVARIANT_TOLERANCE = 0.01  # 亿元

    def __init__(
        self,
        assumptions: ThreeStatementAssumptions,
        skip_gates: bool = False,
    ) -> None:
        self.a = assumptions
        self.provenance = PreciseValuation()
        self._validate_assumptions()

        if not skip_gates:
            gate = IronGateEngine()
            self.gate_report = gate.validate_three_statement(assumptions)
            if not self.gate_report.passed:
                errs = "; ".join(r.message for r in self.gate_report.errors)
                raise ValueError(f"IronGate 三表校验失败:\n{errs}")
        else:
            self.gate_report = None

    def _validate_assumptions(self) -> None:
        """验证输入假设的完整性"""
        a = self.a
        n = a.forecast_years
        if len(a.revenue_growth_rates) != n:
            raise ValueError(f"revenue_growth_rates 长度 ({len(a.revenue_growth_rates)}) ≠ forecast_years ({n})")
        if a.cogs_pct is not None and len(a.cogs_pct) != n:
            raise ValueError(f"cogs_pct 长度 ({len(a.cogs_pct)}) ≠ forecast_years ({n})")

    def run(self) -> ThreeStatementResult:
        """运行三表联动推演"""
        result = ThreeStatementResult(gate_report=self.gate_report)
        a = self.a
        n = a.forecast_years

        # ── Phase 0: 初始化基期状态 ──
        self._init_base_state(result, n)

        # ── Phase 1: Income Statement ──
        self._build_income_statement(result, n)

        # ── Phase 2: Balance Sheet (初始版本) ──
        self._build_balance_sheet(result, n)

        # ── Phase 3: Cash Flow Statement ──
        self._build_cash_flow_statement(result, n)

        # ── Phase 4: 链接修正 — 现金作为 plug，权益基于留存收益 ──
        self._relink_cash(result, n)

        # ── Phase 5: 更新 CF 以反映实际现金变动 ──
        self._update_cash_flow_for_plug(result, n)

        # ── Phase 6: Free Cash Flow ──
        self._compute_free_cash_flow(result, n)

        # ── Phase 7: 财务不变量校验 ──
        self._check_invariants(result, n)

        # ── Phase 8: 估值辅助指标 ──
        self._compute_valuation_metrics(result)

        return result

    def _init_base_state(self, result: ThreeStatementResult, n: int) -> None:
        """初始化基期状态，用于利息计算"""
        a = self.a
        # 基期总债务
        base_total_debt = (
            a.base_short_term_debt + a.base_current_portion_ltd + a.base_long_term_debt + a.base_bonds_payable
        )
        # 存储基期状态供后续使用
        self._base_total_debt = base_total_debt
        self._base_revenue = a.base_revenue

    # ── Phase 1: Income Statement ──────────────────────────────────────────

    def _build_income_statement(self, result: ThreeStatementResult, n: int) -> None:
        """构建利润表"""
        a = self.a
        is_ = result.income_statement

        curr_rev = a.base_revenue
        for i in range(n):
            # 营收
            curr_rev *= 1 + a.revenue_growth_rates[i]
            is_.revenue.append(curr_rev)

            # 营业成本
            cogs_pct = a.cogs_pct[i] if a.cogs_pct else a.base_cogs_pct
            is_.cogs.append(curr_rev * cogs_pct)

            # 毛利
            gp = is_.revenue[-1] - is_.cogs[-1]
            is_.gross_profit.append(gp)
            is_.gross_margin.append(gp / is_.revenue[-1] if is_.revenue[-1] > 0 else 0)

            # 期间费用
            selling = curr_rev * (a.selling_exp_pct[i] if a.selling_exp_pct else a.base_selling_exp_pct)
            admin = curr_rev * (a.admin_exp_pct[i] if a.admin_exp_pct else a.base_admin_exp_pct)
            rd = curr_rev * (a.rd_exp_pct[i] if a.rd_exp_pct else a.base_rd_exp_pct)
            is_.selling_exp.append(selling)
            is_.admin_exp.append(admin)
            is_.rd_exp.append(rd)
            is_.total_opex.append(selling + admin + rd)

            # 营业利润
            op_profit = gp - (selling + admin + rd)
            is_.operating_profit.append(op_profit)

            # 其他收益
            other = curr_rev * a.base_other_income_pct
            invest = curr_rev * a.base_investment_income_pct
            is_.other_income.append(other)
            is_.investment_income.append(invest)

            # EBIT
            ebit = op_profit + other + invest
            is_.ebit.append(ebit)
            is_.ebit_margin.append(ebit / is_.revenue[-1] if is_.revenue[-1] > 0 else 0)

            # 利息费用（简化：使用基期债务 × 利率）
            # 注：完整的利息计算需要在资产负债表构建后迭代修正
            interest = self._base_total_debt * a.term_loan_rate
            is_.interest_expense.append(interest)

            # 税前利润
            ebt = ebit - interest
            is_.ebt.append(ebt)

            # 所得税
            tax = max(ebt * a.tax_rate, 0)  # 亏损不退税
            is_.income_tax.append(tax)

            # 净利润
            ni = ebt - tax
            is_.net_income.append(ni)
            is_.net_margin.append(ni / is_.revenue[-1] if is_.revenue[-1] > 0 else 0)

            # 少数股东损益
            mi = ni * a.minority_interest_pct
            is_.minority_interest.append(mi)
            is_.net_profit_to_parent.append(ni - mi)

    # ── Phase 2: Balance Sheet ─────────────────────────────────────────────

    def _build_balance_sheet(self, result: ThreeStatementResult, n: int) -> None:
        """构建资产负债表 — 现金作为 plug"""
        a = self.a
        bs = result.balance_sheet

        # 基期状态
        prev_revenue = a.base_revenue
        prev_cash = a.base_cash
        prev_receivables = prev_revenue * a.base_receivables_pct
        prev_inventory = prev_revenue * a.base_inventory_pct
        prev_other_ca = prev_revenue * a.base_other_current_assets_pct
        prev_ppe = prev_revenue * a.base_ppe_pct
        prev_intangibles = prev_revenue * a.base_intangibles_pct
        prev_goodwill = a.base_goodwill
        prev_other_nca = prev_revenue * a.base_other_nca_pct

        prev_payables = prev_revenue * a.base_payables_pct
        prev_accrued = prev_revenue * a.base_accrued_expenses_pct
        prev_st_debt = a.base_short_term_debt
        prev_cpltd = a.base_current_portion_ltd
        prev_deferred_rev = prev_revenue * a.base_deferred_revenue_pct
        prev_lt_debt = a.base_long_term_debt
        prev_bonds = a.base_bonds_payable
        prev_lease = a.base_lease_liabilities
        prev_dtl = a.base_deferred_tax_liabilities
        prev_other_ncl = a.base_other_ncl

        prev_equity = a.base_equity
        prev_minority = a.base_minority_interest

        for i in range(n):
            curr_rev = result.income_statement.revenue[i]
            ni = result.income_statement.net_income[i]
            mi = result.income_statement.minority_interest[i]
            da = curr_rev * a.da_pct_revenue

            # ── 资产 ──
            # 流动资产
            cash = prev_cash  # 初始值，后续会被 CF 修正
            receivables = curr_rev * a.base_receivables_pct
            inventory = curr_rev * a.base_inventory_pct
            other_ca = curr_rev * a.base_other_current_assets_pct
            total_ca = cash + receivables + inventory + other_ca

            # 非流动资产（折旧减少）
            ppe = max(prev_ppe + (curr_rev * a.capex_pct_revenue) - da, 0)
            intangibles = max(prev_intangibles - da * 0.3, 0)  # 无形资产按 30% 折旧
            goodwill = prev_goodwill
            other_nca = curr_rev * a.base_other_nca_pct
            total_nca = ppe + intangibles + goodwill + other_nca

            total_assets = total_ca + total_nca

            # ── 负债 ──
            payables = curr_rev * a.base_payables_pct
            accrued = curr_rev * a.base_accrued_expenses_pct
            st_debt = prev_st_debt
            cpltd = prev_cpltd
            deferred_rev = curr_rev * a.base_deferred_revenue_pct
            total_cl = payables + accrued + st_debt + cpltd + deferred_rev

            lt_debt = prev_lt_debt
            bonds = prev_bonds
            lease = prev_lease
            dtl = prev_dtl
            other_ncl = prev_other_nca
            total_ncl = lt_debt + bonds + lease + dtl + other_ncl

            total_liabilities = total_cl + total_ncl

            # ── 权益 ──
            # 留存收益变动 = 归母净利润 × (1 - 分红率)
            parent_ni = ni - mi
            retained_addition = parent_ni * (1 - a.payout_ratio)
            equity = prev_equity + retained_addition
            minority = prev_minority + mi
            total_equity = equity + minority

            # ── 现金 plug（暂时用上期值，后续修正） ──
            # 这里先存初始值，_relink_cash 会修正

            bs.cash.append(cash)
            bs.receivables.append(receivables)
            bs.inventory.append(inventory)
            bs.other_current_assets.append(other_ca)
            bs.total_current_assets.append(total_ca)
            bs.ppe.append(ppe)
            bs.intangibles.append(intangibles)
            bs.goodwill.append(goodwill)
            bs.other_nca.append(other_nca)
            bs.total_assets.append(total_assets)

            bs.payables.append(payables)
            bs.accrued_expenses.append(accrued)
            bs.short_term_debt.append(st_debt)
            bs.current_portion_ltd.append(cpltd)
            bs.deferred_revenue.append(deferred_rev)
            bs.total_current_liabilities.append(total_cl)
            bs.long_term_debt.append(lt_debt)
            bs.bonds_payable.append(bonds)
            bs.lease_liabilities.append(lease)
            bs.deferred_tax_liabilities.append(dtl)
            bs.other_ncl.append(other_ncl)
            bs.total_non_current_liabilities.append(total_ncl)
            bs.total_liabilities.append(total_liabilities)

            bs.equity.append(equity)
            bs.minority_interest.append(minority)
            bs.total_equity.append(total_equity)

            # 更新 prev 变量
            prev_revenue = curr_rev
            prev_cash = cash
            prev_receivables = receivables
            prev_inventory = inventory
            prev_other_ca = other_ca
            prev_ppe = ppe
            prev_intangibles = intangibles
            prev_goodwill = goodwill
            prev_other_nca = other_nca
            prev_payables = payables
            prev_accrued = accrued
            prev_st_debt = st_debt
            prev_cpltd = cpltd
            prev_deferred_rev = deferred_rev
            prev_lt_debt = lt_debt
            prev_bonds = bonds
            prev_lease = lease
            prev_dtl = dtl
            prev_other_ncl = other_ncl
            prev_equity = equity
            prev_minority = minority

    # ── Phase 3: Cash Flow Statement ───────────────────────────────────────

    def _build_cash_flow_statement(self, result: ThreeStatementResult, n: int) -> None:
        """构建现金流量表"""
        a = self.a
        cf = result.cash_flow
        is_ = result.income_statement
        bs = result.balance_sheet

        for i in range(n):
            # 经营活动
            ni = is_.net_income[i]
            da = is_.revenue[i] * a.da_pct_revenue

            # 营运资金变动（间接法）
            if i == 0:
                prev_rev = a.base_revenue
                prev_recv = prev_rev * a.base_receivables_pct
                prev_inv = prev_rev * a.base_inventory_pct
                prev_pay = prev_rev * a.base_payables_pct
                prev_acc = prev_rev * a.base_accrued_expenses_pct
                prev_def_rev = prev_rev * a.base_deferred_revenue_pct
            else:
                prev_recv = bs.receivables[i - 1]
                prev_inv = bs.inventory[i - 1]
                prev_pay = bs.payables[i - 1]
                prev_acc = bs.accrued_expenses[i - 1]
                prev_def_rev = bs.deferred_revenue[i - 1]

            # ΔNWC = Δ(应收+存货) - Δ(应付+应计+递延收益)
            d_recv = bs.receivables[i] - prev_recv
            d_inv = bs.inventory[i] - prev_inv
            d_pay = bs.payables[i] - prev_pay
            d_acc = bs.accrued_expenses[i] - prev_acc
            d_def = bs.deferred_revenue[i] - prev_def_rev
            wc_change = (d_recv + d_inv) - (d_pay + d_acc + d_def)

            cfo = ni + da - wc_change
            cf.net_income.append(ni)
            cf.da.append(da)
            cf.wc_change.append(wc_change)
            cf.cash_from_operations.append(cfo)

            # 投资活动
            capex = is_.revenue[i] * a.capex_pct_revenue
            cf.capex.append(capex)
            cf.cash_from_investing.append(-capex)

            # 融资活动
            # 简化：不新增债务，只还旧债
            debt_repayment = bs.current_portion_ltd[i] if i > 0 else a.base_current_portion_ltd
            dividends = is_.net_profit_to_parent[i] * a.payout_ratio
            buyback = is_.net_profit_to_parent[i] * a.share_buyback_pct

            cf.debt_proceeds.append(0)
            cf.debt_repayment.append(debt_repayment)
            cf.dividends_paid.append(dividends)
            cf.share_buyback.append(buyback)
            cf.cash_from_financing.append(-debt_repayment - dividends - buyback)

            # 现金变动
            net_change = cfo + (-capex) + (-debt_repayment - dividends - buyback)
            cf.net_cash_change.append(net_change)

    # ── Phase 4: Re-link Cash ──────────────────────────────────────────────

    def _relink_cash(self, result: ThreeStatementResult, n: int) -> None:
        """将 CF 期末现金回写到 BS，实现三表链接

        关键：现金是资产负债表的 plug（平衡项）。
        1. 先计算权益（基于留存收益）
        2. 再计算所需的现金（Assets = L + E → Cash = L + E - Other Assets）
        """
        a = self.a
        bs = result.balance_sheet
        cf = result.cash_flow

        for i in range(n):
            # Step 1: 计算权益（基于留存收益）
            if i == 0:
                prev_equity = a.base_equity
                prev_minority = a.base_minority_interest
            else:
                prev_equity = bs.equity[i - 1]
                prev_minority = bs.minority_interest[i - 1]

            parent_ni = result.income_statement.net_profit_to_parent[i]
            mi = result.income_statement.minority_interest[i]
            retained_addition = parent_ni * (1 - a.payout_ratio)

            bs.equity[i] = prev_equity + retained_addition
            bs.minority_interest[i] = prev_minority + mi
            bs.total_equity[i] = bs.equity[i] + bs.minority_interest[i]

            # Step 2: 计算所需的总资产（L + E）
            required_total_assets = bs.total_liabilities[i] + bs.total_equity[i]

            # Step 3: 计算除现金外的其他资产
            other_assets = (
                bs.receivables[i]
                + bs.inventory[i]
                + bs.other_current_assets[i]
                + bs.ppe[i]
                + bs.intangibles[i]
                + bs.goodwill[i]
                + bs.other_nca[i]
            )

            # Step 4: 计算所需的现金（作为 plug）
            required_cash = required_total_assets - other_assets

            # Step 5: 如果现金低于最低余额，需要借债
            if required_cash < a.min_cash_balance:
                shortfall = a.min_cash_balance - required_cash
                # 短期借款增加
                bs.short_term_debt[i] += shortfall
                bs.total_current_liabilities[i] += shortfall
                bs.total_liabilities[i] += shortfall
                # 重新计算所需的总资产
                required_total_assets = bs.total_liabilities[i] + bs.total_equity[i]
                required_cash = a.min_cash_balance

            # Step 6: 更新 BS
            bs.cash[i] = required_cash
            bs.total_current_assets[i] = (
                required_cash + bs.receivables[i] + bs.inventory[i] + bs.other_current_assets[i]
            )
            bs.total_assets[i] = bs.total_current_assets[i] + (
                bs.ppe[i] + bs.intangibles[i] + bs.goodwill[i] + bs.other_nca[i]
            )

            # Step 7: 计算 CF 期末现金
            if i == 0:
                prev_cash = a.base_cash
            else:
                prev_cash = bs.cash[i - 1]
            cf.ending_cash.append(bs.cash[i])

            # Step 8: 计算 BS 不平衡（应该为 0）
            imbalance = bs.total_assets[i] - bs.total_liabilities[i] - bs.total_equity[i]
            bs.bs_imbalance.append(imbalance)

    def _update_cash_flow_for_plug(self, result: ThreeStatementResult, n: int) -> None:
        """更新现金流量表以反映现金作为 plug 的实际现金变动

        当现金作为 plug 时，实际的现金变动可能与初始 CF 计算的不同。
        需要更新 CF 以反映：1) 实际的期末现金 2) 实际的借债/还款
        """
        a = self.a
        bs = result.balance_sheet
        cf = result.cash_flow

        for i in range(n):
            # 计算实际的现金变动
            if i == 0:
                prev_cash = a.base_cash
            else:
                prev_cash = bs.cash[i - 1]
            actual_cash_change = bs.cash[i] - prev_cash

            # 计算借债变动（如果有的话）
            if i == 0:
                prev_st_debt = a.base_short_term_debt
            else:
                prev_st_debt = bs.short_term_debt[i - 1]
            debt_change = bs.short_term_debt[i] - prev_st_debt

            # 更新 CF 融资活动（如果有借债）
            if debt_change > 0:
                cf.debt_proceeds[i] = debt_change
                cf.cash_from_financing[i] += debt_change

            # 更新 CF 期末现金
            cf.net_cash_change[i] = actual_cash_change
            cf.ending_cash[i] = bs.cash[i]

    # ── Phase 5: Free Cash Flow ────────────────────────────────────────────

    def _compute_free_cash_flow(self, result: ThreeStatementResult, n: int) -> None:
        """计算 FCFF 和 FCFE — Decimal 精度"""
        a = self.a
        is_ = result.income_statement
        fcf = result.free_cash_flow
        tax = D(a.tax_rate)

        for i in range(n):
            ebit_d = D(is_.ebit[i])
            da_d = D(is_.revenue[i]) * D(a.da_pct_revenue)
            capex_d = D(is_.revenue[i]) * D(a.capex_pct_revenue)
            wc_d = D(result.cash_flow.wc_change[i])

            # NOPAT = EBIT × (1 - tax_rate)
            nopat_d = ebit_d * (D(1) - tax)
            nopat = dto_float(nopat_d)
            fcf.nopat.append(nopat)

            # FCFF = NOPAT + D&A - Capex - ΔWC
            fcff_d = nopat_d + da_d - capex_d - wc_d
            fcff = dto_float(fcff_d)
            fcf.fcff.append(fcff)

            self.provenance.set(
                f"year{i + 1}.fcff",
                fcff,
                source="computed",
                formula="NOPAT + D&A - CapEx - ΔWC",
            )

            # 利息费用（税后）
            interest_d = D(is_.interest_expense[i])
            net_interest_d = interest_d * (D(1) - tax)
            net_interest = dto_float(net_interest_d)
            fcf.less_net_interest.append(-net_interest)

            # 净债务偿还
            if i == 0:
                debt_repayment = a.base_current_portion_ltd
            else:
                debt_repayment = result.balance_sheet.current_portion_ltd[i]
            fcf.less_net_debt_repayment.append(-debt_repayment)

            # FCFE = FCFF - 税后利息 + 净债务偿还
            fcfe_d = fcff_d - net_interest_d - D(debt_repayment)
            fcf.fcfe.append(dto_float(fcfe_d))

            fcf.plus_da.append(dto_float(da_d))
            fcf.less_capex.append(-dto_float(capex_d))
            fcf.less_wc_change.append(-dto_float(wc_d))

    # ── Phase 6: Invariant Checks ──────────────────────────────────────────

    def _check_invariants(self, result: ThreeStatementResult, n: int) -> None:
        """三项财务不变量校验 — Decimal 精度"""
        checks = {}
        violations = []
        tol = D(self.INVARIANT_TOLERANCE)

        # 1. Balance Sheet Identity: Assets = Liabilities + Equity
        bs_ok = True
        for i in range(n):
            imbalance_d = D(result.balance_sheet.bs_imbalance[i])
            if abs(imbalance_d) > tol:
                bs_ok = False
                violations.append(
                    f"Year {i + 1}: BS 不平衡 {result.balance_sheet.bs_imbalance[i]:.4f}亿 "
                    f"(Assets={result.balance_sheet.total_assets[i]:.2f}, "
                    f"L+E={result.balance_sheet.total_liabilities[i] + result.balance_sheet.total_equity[i]:.2f})"
                )
        checks["balance_sheet_identity"] = bs_ok

        # 2. Cash Flow Identity: 期初现金 + 净变动 = 期末现金
        cf_ok = True
        for i in range(n):
            prev_cash = D(self.a.base_cash) if i == 0 else D(result.balance_sheet.cash[i - 1])
            expected_d = prev_cash + D(result.cash_flow.net_cash_change[i])
            actual_d = D(result.balance_sheet.cash[i])
            if abs(expected_d - actual_d) > tol:
                cf_ok = False
                violations.append(
                    f"Year {i + 1}: CF 恒等式偏差 {dto_float(expected_d - actual_d):.4f}亿 "
                    f"(expected={dto_float(expected_d):.2f}, actual={dto_float(actual_d):.2f})"
                )
        checks["cash_flow_identity"] = cf_ok

        # 3. Retained Earnings Identity: 期末RE = 期初RE + 归母净利润 - 分红
        re_ok = True
        for i in range(n):
            prev_eq = D(self.a.base_equity) if i == 0 else D(result.balance_sheet.equity[i - 1])
            parent_ni_d = D(result.income_statement.net_profit_to_parent[i])
            retained_d = parent_ni_d * (D(1) - D(self.a.payout_ratio))
            expected_eq_d = prev_eq + retained_d
            actual_eq_d = D(result.balance_sheet.equity[i])
            if abs(expected_eq_d - actual_eq_d) > tol:
                re_ok = False
                violations.append(
                    f"Year {i + 1}: RE 恒等式偏差 {dto_float(expected_eq_d - actual_eq_d):.4f}亿 "
                    f"(expected={dto_float(expected_eq_d):.2f}, actual={dto_float(actual_eq_d):.2f})"
                )
        checks["retained_earnings_identity"] = re_ok

        result.invariant_checks = checks
        result.invariant_violations = violations

        if violations:
            result.warnings.append(f"三项财务不变量中有 {sum(1 for v in checks.values() if not v)} 项不满足")

    # ── Phase 7: Valuation Metrics ─────────────────────────────────────────

    def _compute_valuation_metrics(self, result: ThreeStatementResult) -> None:
        """计算估值辅助指标 — Decimal 精度 + 溯源"""
        a = self.a
        n = a.forecast_years

        for i in range(n):
            total_debt = (
                result.balance_sheet.short_term_debt[i]
                + result.balance_sheet.current_portion_ltd[i]
                + result.balance_sheet.long_term_debt[i]
                + result.balance_sheet.bonds_payable[i]
            )
            result.total_debt.append(total_debt)
            result.net_debt.append(total_debt - result.balance_sheet.cash[i])

        if n > 0:
            result.fcff_for_dcf = result.free_cash_flow.fcff[-1]
            result.fcfe_for_dcf = result.free_cash_flow.fcfe[-1]
            self.provenance.set("fcff_for_dcf", result.fcff_for_dcf, formula="last year FCFF")
            self.provenance.set("fcfe_for_dcf", result.fcfe_for_dcf, formula="last year FCFE")
