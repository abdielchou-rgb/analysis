#!/usr/bin/env python3
"""
engine 独立演示流水线 — 展示 P0-P3 全部功能。
可直接运行: python -m engine.main
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.comparable_model import ComparableEngine
from engine.dcf_model import DCFEngine
from engine.debate import DevilAdvocateAgent
from engine.excel_writer import AuditExcelWriter
from engine.fcff_path import FCFFPathEngine, MarketImpliedSolver
from engine.irongate import IronGateEngine
from engine.knowledge import DamodaranEntry, DamodaranRAG, DamodaranRAGQuery, TickerMemoryStore
from engine.mcp_tools import MCPEngine

# P2 imports
from engine.monte_carlo import MonteCarloAssumptions, MonteCarloEngine

# P3 imports
from engine.orchestrator import IBGradeOrchestrator

# P1 imports
from engine.precision import PreciseValuation
from engine.regime import (
    PeerComponent,
    RegimeAssumptions,
    RegimeDCFEngine,
    SyntheticPeerAssumptions,
    SyntheticPeerEngine,
)
from engine.scenario_model import ScenarioEngine
from engine.schemas import (
    ComparableAssumptions,
    DCFAssumptions,
    ScenarioAssumptions,
    ScenarioDetail,
    SOTPAssumptions,
    SOTPSegment,
    ValuationMethod,
)
from engine.sotp_model import SOTPEngine
from engine.three_statement import ThreeStatementAssumptions, ThreeStatementEngine
from engine.valuation_catalog import (
    IndustryType,
    IndustryValuationAssumptions,
    IndustryValuationEngine,
    ValuationCatalog,
)

# ─── 示例数据 ───────────────────────────────────────────────────────────────

TICKER = "600519.SH"
COMPANY = "贵州茅台"

DCF_EXAMPLE = DCFAssumptions(
    ticker=TICKER,
    company_name=COMPANY,
    forecast_years=5,
    base_revenue=1500.0,
    base_ebit_margin=0.65,
    revenue_growth_rates=[0.15, 0.12, 0.10, 0.08, 0.06],
    ebit_margins=[0.65, 0.66, 0.66, 0.67, 0.67],
    da_pct_revenue=0.02,
    capex_pct_revenue=0.03,
    wc_pct_revenue=0.01,
    tax_rate=0.25,
    wacc=0.085,
    terminal_growth_rate=0.03,
    net_debt=-500.0,
    shares_outstanding=12.56,
    current_price=1680.0,
    risk_free_rate=0.025,
    equity_risk_premium=0.065,
    beta=0.75,
)

COMPARABLE_EXAMPLE = ComparableAssumptions(
    ticker=TICKER,
    company_name=COMPANY,
    company_eps=60.0,
    company_bvps=200.0,
    company_revenue_per_share=120.0,
    company_ebitda_per_share=80.0,
    peer_pe_ratios=[28.5, 32.1, 25.8, 30.2, 27.9, 35.0, 22.5],
    peer_pb_ratios=[8.5, 10.2, 7.8, 9.1, 8.0],
    peer_ps_ratios=[12.5, 15.0, 10.8, 13.2, 11.5],
)

SCENARIO_EXAMPLE = ScenarioAssumptions(
    ticker=TICKER,
    company_name=COMPANY,
    base_price=1680.0,
    bull=ScenarioDetail(
        revenue_growth_rates=[0.18, 0.15, 0.12, 0.10, 0.08],
        operating_margin=0.68,
        terminal_growth=0.035,
        probability=0.25,
    ),
    base=ScenarioDetail(
        revenue_growth_rates=[0.12, 0.10, 0.08, 0.06, 0.05],
        operating_margin=0.65,
        terminal_growth=0.03,
        probability=0.55,
    ),
    bear=ScenarioDetail(
        revenue_growth_rates=[0.05, 0.04, 0.03, 0.02, 0.02],
        operating_margin=0.58,
        terminal_growth=0.025,
        probability=0.20,
    ),
    wacc=0.085,
    projection_years=5,
    tax_rate=0.25,
    base_revenue=1500.0,
    total_shares=12.56,
    net_debt=-500.0,
)

SOTP_EXAMPLE = SOTPAssumptions(
    ticker=TICKER,
    company_name=COMPANY,
    segments=[
        SOTPSegment(
            name="茅台酒（高端）", revenue=1200.0, profit=600.0, valuation_method=ValuationMethod.PE, peer_multiple=30.0
        ),
        SOTPSegment(
            name="系列酒（中端）", revenue=200.0, profit=50.0, valuation_method=ValuationMethod.PE, peer_multiple=20.0
        ),
        SOTPSegment(
            name="金融业务", revenue=100.0, profit=30.0, valuation_method=ValuationMethod.PE, peer_multiple=12.0
        ),
    ],
    cash_and_equivalents=600.0,
    net_debt=-500.0,
    non_core_assets=50.0,
    total_shares=12.56,
    current_price=1680.0,
)

THREE_STATEMENT_EXAMPLE = ThreeStatementAssumptions(
    ticker=TICKER,
    company_name=COMPANY,
    forecast_years=5,
    base_revenue=1500.0,
    base_cogs_pct=0.10,
    base_selling_exp_pct=0.03,
    base_admin_exp_pct=0.05,
    base_rd_exp_pct=0.01,
    tax_rate=0.25,
    minority_interest_pct=0.03,
    base_cash=500.0,
    base_receivables_pct=0.15,
    base_inventory_pct=0.10,
    base_other_current_assets_pct=0.02,
    base_ppe_pct=0.30,
    base_intangibles_pct=0.05,
    base_goodwill=0.0,
    base_other_nca_pct=0.02,
    base_payables_pct=0.12,
    base_accrued_expenses_pct=0.03,
    base_short_term_debt=0.0,
    base_current_portion_ltd=0.0,
    base_long_term_debt=0.0,
    base_bonds_payable=0.0,
    base_lease_liabilities=0.0,
    base_deferred_tax_liabilities=0.0,
    base_other_ncl=0.0,
    base_equity=1150.0,
    base_minority_interest=55.0,
    revenue_growth_rates=[0.12, 0.10, 0.08, 0.06, 0.05],
    cogs_pct=[0.10] * 5,
    selling_exp_pct=[0.03] * 5,
    admin_exp_pct=[0.05] * 5,
    rd_exp_pct=[0.01] * 5,
    da_pct_revenue=0.02,
    capex_pct_revenue=0.03,
    payout_ratio=0.50,
    min_cash_balance=100.0,
    revolver_rate=0.04,
    term_loan_rate=0.05,
)


def run_demo():
    print("=" * 70)
    print("  engine v2.0 — P0-P3 全功能演示")
    print("=" * 70)

    # ══════════════════════════════════════════════════════════════════════
    # P0: 核心估值引擎
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P0: 核心估值引擎")
    print("─" * 70)

    gate = IronGateEngine()
    reports = gate.validate_all(
        dcf=DCF_EXAMPLE, comparable=COMPARABLE_EXAMPLE, scenario=SCENARIO_EXAMPLE, sotp=SOTP_EXAMPLE
    )
    for name, report in reports.items():
        print(f"  IronGate {name}: {'PASS' if report.passed else 'FAIL'}")

    dcf_result = DCFEngine(DCF_EXAMPLE, skip_gates=True).run()
    comp_result = ComparableEngine(COMPARABLE_EXAMPLE, skip_gates=True).run()
    scn_result = ScenarioEngine(SCENARIO_EXAMPLE, skip_gates=True).run()
    sotp_result = SOTPEngine(SOTP_EXAMPLE, skip_gates=True).run()
    ts_result = ThreeStatementEngine(THREE_STATEMENT_EXAMPLE, skip_gates=True).run()

    print(f"  DCF:         {dcf_result.fair_value_per_share:>8.2f} 元/股")
    print(f"  Comparable:  {comp_result.target_price:>8.2f} 元/股")
    print(f"  Scenario:    {scn_result.weighted_target:>8.2f} 元/股")
    print(f"  SOTP:        {sotp_result.target_price:>8.2f} 元/股")
    print(f"  Three-Stmt:  FCFF={ts_result.fcff_for_dcf:.0f} 亿")

    # ══════════════════════════════════════════════════════════════════════
    # P1: Decimal 精度
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P1: Decimal 精度层")
    print("─" * 70)

    pv = PreciseValuation()
    pv.set("revenue", 1500.0, source="financial_statement", formula="base_revenue")
    pv.set("ebit_margin", 0.65, source="assumption", formula="LLM_extracted")
    pv.set("ebit", "1500 * 0.65", source="computed", formula="revenue × margin")
    print(f"  EBIT: {pv.get('revenue')}")
    print(pv.provenance_report())

    # ══════════════════════════════════════════════════════════════════════
    # P1: Regime-Conditional DCF
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P1: Regime-Conditional DCF")
    print("─" * 70)

    regime_a = RegimeAssumptions(
        ticker=TICKER,
        company_name=COMPANY,
        base_revenue=1500.0,
        base_ebit_margin=0.65,
        forecast_years=5,
        revenue_growth_rates=[0.15, 0.12, 0.10, 0.08, 0.06],
        ebit_margins=[0.65, 0.66, 0.66, 0.67, 0.67],
        wacc=0.085,
        terminal_growth_rate=0.03,
        net_debt=-500.0,
        shares_outstanding=12.56,
        current_price=1680.0,
    )
    regime_result = RegimeDCFEngine(regime_a).run()
    print(f"  加权目标价:  {regime_result.weighted_value:.2f} 元/股")
    for regime, value in regime_result.regime_values.items():
        prob = regime_result.regime_probabilities[regime]
        print(f"    {regime:>12}: {value:>8.2f} (概率 {prob:.0%})")

    # ══════════════════════════════════════════════════════════════════════
    # P1: Synthetic Peers
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P1: Synthetic Peers")
    print("─" * 70)

    synth_a = SyntheticPeerAssumptions(
        ticker=TICKER,
        company_name=COMPANY,
        company_eps=60.0,
        company_bvps=200.0,
        components=[
            PeerComponent("高端白酒", 0.6, 30.0, 9.0, 12.0, 20.0),
            PeerComponent("大众消费品", 0.3, 22.0, 4.0, 3.0, 12.0),
            PeerComponent("金融控股", 0.1, 10.0, 1.2, 2.0, 8.0),
        ],
    )
    synth_result = SyntheticPeerEngine(synth_a).run()
    print(f"  合成 PE: {synth_result.synthetic_pe:.2f}")
    for method, price in synth_result.implied_prices.items():
        print(f"    {method} 隐含: {price:.2f} 元")
    print(f"  综合目标价: {synth_result.target_price:.2f} 元/股")

    # ══════════════════════════════════════════════════════════════════════
    # P1: FCFF Path + Market-Implied g
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P1: FCFF Path + Market-Implied Growth")
    print("─" * 70)

    fcff_engine = FCFFPathEngine()
    fcff_result = fcff_engine.compute_both_paths(
        ebit=975.0,
        tax_rate=0.25,
        da=30.0,
        capex=45.0,
        wc_change=15.0,
        cfo=950.0,
        interest_expense=0.0,
    )
    print(f"  EBIAT 路径 FCFF: {fcff_result.fcff:.2f} 亿")
    if fcff_result.fcff_from_cfo is not None:
        print(f"  CFO 路径 FCFF:   {fcff_result.fcff_from_cfo:.2f} 亿")
        print(f"  路径差异:        {fcff_result.path_diff:.2f} 亿 ({fcff_result.path_diff_pct:.1f}%)")

    solver = MarketImpliedSolver()
    implied = solver.solve(
        current_price=1680.0,
        shares_outstanding=12.56,
        net_debt=-500.0,
        current_fcf=1174.0,
        wacc=0.085,
        terminal_growth=0.03,
    )
    print(f"  隐含增长率: {implied.implied_growth:.2%}")
    print(f"  隐含 EV:    {implied.implied_ev:.0f} 亿")

    # ══════════════════════════════════════════════════════════════════════
    # P1: Devil's Advocate Debate
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P1: Devil's Advocate Debate")
    print("─" * 70)

    devil = DevilAdvocateAgent()
    challenge = devil.challenge(
        bull_thesis="茅台受益于消费升级，DCF 估值 1513 元",
        evidence=["ROE > 30%", "营收增长稳定"],
        financials={"debt_ratio": 0.05, "revenue_growth": 0.12, "margin": 0.65, "pe_ratio": 28},
    )
    print(f"  反方挑战: {challenge.thesis}")
    print(f"  识别风险: {', '.join(challenge.risks[:3])}")

    # ══════════════════════════════════════════════════════════════════════
    # P2: Monte Carlo
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P2: Monte Carlo Simulation (10,000 runs)")
    print("─" * 70)

    mc_a = MonteCarloAssumptions(
        ticker=TICKER,
        company_name=COMPANY,
        n_simulations=10000,
        seed=42,
        base_revenue=1500.0,
        revenue_growth_mean=0.10,
        revenue_growth_std=0.03,
        ebit_margin_mean=0.65,
        ebit_margin_std=0.02,
        wacc_mean=0.085,
        wacc_std=0.01,
        terminal_growth_mean=0.03,
        terminal_growth_std=0.005,
        forecast_years=5,
        net_debt=-500.0,
        shares_outstanding=12.56,
        current_price=1680.0,
    )
    mc_result = MonteCarloEngine(mc_a).run()
    print(f"  均值:   {mc_result.mean:.2f}")
    print(f"  中位数: {mc_result.median:.2f}")
    print(f"  标准差: {mc_result.std:.2f}")
    print(f"  95% CI: [{mc_result.confidence_interval_95[0]:.2f}, {mc_result.confidence_interval_95[1]:.2f}]")
    if mc_result.prob_above_current is not None:
        print(f"  P(>当前价): {mc_result.prob_above_current:.1%}")
    print(f"  敏感性排序: {', '.join(f'{k}({v:.2f})' for k, v in mc_result.sensitivity_ranking)}")

    # ══════════════════════════════════════════════════════════════════════
    # P2: Quality Scoring
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P2: Quality Scoring")
    print("─" * 70)

    piotroski = ValuationCatalog.piotroski_f_score(
        {
            "roa": 0.25,
            "cfo": 1.0,
            "roa_change": 0.02,
            "cfo > net_income": 1,
            "leverage_change": -0.05,
            "current_ratio_change": 0.1,
            "shares_change": -0.02,
            "gross_margin_change": 0.01,
            "asset_turnover_change": 0.05,
        }
    )
    altman = ValuationCatalog.altman_z_score(
        assets=2500,
        liabilities=800,
        working_capital=1200,
        retained_earnings=800,
        ebit=975,
        market_cap=21100,
        total_revenue=1500,
    )
    print(f"  Piotroski F-Score: {piotroski}/9")
    print(f"  Altman Z-Score:    {altman:.2f} (>2.99=Safe)")

    # ══════════════════════════════════════════════════════════════════════
    # P2: Industry-Aware Valuation
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P2: Industry-Aware Valuation")
    print("─" * 70)

    bank_a = IndustryValuationAssumptions(
        ticker="601398.SH",
        company_name="工商银行",
        industry=IndustryType.BANK,
        book_value_per_share=7.5,
        roe=0.12,
        cost_of_equity=0.09,
        growth_rate=0.03,
        shares=3564.0,
    )
    bank_result = IndustryValuationEngine(bank_a).run()
    print(f"  银行估值 ({bank_result.method_used}): {bank_result.target_price:.2f} 元/股")

    # ══════════════════════════════════════════════════════════════════════
    # P2: Damodaran RAG + Ticker Memory
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P2: Damodaran RAG + Ticker Memory")
    print("─" * 70)

    rag = DamodaranRAG()
    rag.add_entry(DamodaranEntry("1", "blog", "dcf", "WACC should reflect the risk of the cash flows"))
    rag_result = rag.query(DamodaranRAGQuery("WACC discount rate"))
    print(f"  RAG 查询: 找到 {len(rag_result.entries)} 条相关条目")

    memory = TickerMemoryStore()
    mem = memory.get(TICKER)
    mem.investment_thesis = "白酒龙头，品牌护城河深厚"
    memory.add_history(TICKER, {"date": "2026-01", "action": "initiate", "price": 1680})
    print(f"  Ticker 记忆: {mem.investment_thesis}")

    # ══════════════════════════════════════════════════════════════════════
    # P3: MCP Tools
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P3: MCP Tools")
    print("─" * 70)

    mcp = MCPEngine()
    tools = mcp.list_tools()
    print(f"  注册工具: {len(tools)} 个")
    for tool in tools:
        print(f"    - {tool.name}: {tool.description[:40]}...")

    # ══════════════════════════════════════════════════════════════════════
    # P3: 16-Step Orchestrator
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  P3: 16-Step IB-Grade Orchestrator")
    print("─" * 70)

    orchestrator = IBGradeOrchestrator()
    pipeline_result = orchestrator.run({"ticker": TICKER, "base_revenue": 1500.0, "wacc": 0.085})
    completed = sum(1 for s in pipeline_result.steps.values() if s.status == "completed")
    print(f"  管线状态: {completed}/{len(pipeline_result.steps)} 步完成")
    print(f"  总耗时: {pipeline_result.total_duration_ms:.0f}ms")

    # ══════════════════════════════════════════════════════════════════════
    # Excel 导出
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("  Excel 审计底稿导出")
    print("─" * 70)

    writer = AuditExcelWriter(
        dcf_assumptions=DCF_EXAMPLE,
        comparable_assumptions=COMPARABLE_EXAMPLE,
        scenario_assumptions=SCENARIO_EXAMPLE,
        sotp_assumptions=SOTP_EXAMPLE,
        three_statement_result=ts_result,
    )
    outpath = writer.export("output/audit_valuation_model.xlsx")
    print(f"  成功生成: {outpath}")

    # ══════════════════════════════════════════════════════════════════════
    # 汇总
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  全方法估值汇总")
    print("=" * 70)
    print(f"  DCF:              {dcf_result.fair_value_per_share:>8.2f} 元/股")
    print(f"  Comparable:       {comp_result.target_price:>8.2f} 元/股")
    print(f"  Scenario:         {scn_result.weighted_target:>8.2f} 元/股")
    print(f"  SOTP:             {sotp_result.target_price:>8.2f} 元/股")
    print(f"  Regime DCF:       {regime_result.weighted_value:>8.2f} 元/股")
    print(f"  Synthetic Peer:   {synth_result.target_price:>8.2f} 元/股")
    print(f"  Monte Carlo:      {mc_result.median:>8.2f} 元/股 (中位数)")
    print(f"  Bank DDM:         {bank_result.target_price:>8.2f} 元/股")

    all_prices = [
        dcf_result.fair_value_per_share,
        comp_result.target_price,
        scn_result.weighted_target,
        sotp_result.target_price,
        regime_result.weighted_value,
        synth_result.target_price,
        mc_result.median,
    ]
    avg = sum(all_prices) / len(all_prices)
    print("  ─────────────────────────────────")
    print(f"  综合均值:         {avg:>8.2f} 元/股")
    if DCF_EXAMPLE.current_price:
        upside = (avg / DCF_EXAMPLE.current_price - 1) * 100
        print(f"  vs 当前价:        {DCF_EXAMPLE.current_price:.0f} → {upside:+.1f}%")
    print()


if __name__ == "__main__":
    run_demo()
