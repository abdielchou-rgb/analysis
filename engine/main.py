#!/usr/bin/env python3
"""
engine 独立演示流水线 — 展示四大估值引擎 + Excel 审计底稿导出。
可直接运行: python -m engine.main
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 engine 包可被导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.comparable_model import ComparableEngine
from engine.dcf_model import DCFEngine
from engine.excel_writer import AuditExcelWriter
from engine.irongate import IronGateEngine
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

# ─── 示例数据 ───────────────────────────────────────────────────────────────

DCF_EXAMPLE = DCFAssumptions(
    ticker="600519.SH",
    company_name="贵州茅台",
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
    net_debt=-500.0,  # 茅台几乎零负债，大量现金
    shares_outstanding=12.56,
    current_price=1680.0,
    risk_free_rate=0.025,
    equity_risk_premium=0.065,
    beta=0.75,
)

COMPARABLE_EXAMPLE = ComparableAssumptions(
    ticker="600519.SH",
    company_name="贵州茅台",
    company_eps=60.0,
    company_bvps=200.0,
    company_revenue_per_share=120.0,
    company_ebitda_per_share=80.0,
    peer_pe_ratios=[28.5, 32.1, 25.8, 30.2, 27.9, 35.0, 22.5],
    peer_pb_ratios=[8.5, 10.2, 7.8, 9.1, 8.0],
    peer_ps_ratios=[12.5, 15.0, 10.8, 13.2, 11.5],
)

SCENARIO_EXAMPLE = ScenarioAssumptions(
    ticker="600519.SH",
    company_name="贵州茅台",
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
    ticker="600519.SH",
    company_name="贵州茅台",
    segments=[
        SOTPSegment(
            name="茅台酒（高端）",
            revenue=1200.0,
            profit=600.0,
            valuation_method=ValuationMethod.PE,
            peer_multiple=30.0,
            description="飞天茅台、生肖酒等高端产品线",
        ),
        SOTPSegment(
            name="系列酒（中端）",
            revenue=200.0,
            profit=50.0,
            valuation_method=ValuationMethod.PE,
            peer_multiple=20.0,
            description="茅台王子、茅台迎宾等系列酒",
        ),
        SOTPSegment(
            name="金融业务",
            revenue=100.0,
            profit=30.0,
            valuation_method=ValuationMethod.PE,
            peer_multiple=12.0,
            description="财务公司、基金等金融板块",
        ),
    ],
    cash_and_equivalents=600.0,
    net_debt=-500.0,  # 净现金
    non_core_assets=50.0,
    total_shares=12.56,
    current_price=1680.0,
)


def run_demo():
    print("=" * 60)
    print("  engine 独立估值引擎 — 完整演示")
    print("=" * 60)

    # ── Step 1: IronGate 预检 ───────────────────────────────────────────
    print("\n[Step 1] IronGate 假设预检...")
    gate = IronGateEngine()
    reports = gate.validate_all(
        dcf=DCF_EXAMPLE,
        comparable=COMPARABLE_EXAMPLE,
        scenario=SCENARIO_EXAMPLE,
        sotp=SOTP_EXAMPLE,
    )
    all_passed = True
    for name, report in reports.items():
        status = "PASS" if report.passed else "FAIL"
        print(f"  {name}: {status} ({len(report.results)} gates)")
        if not report.passed:
            all_passed = False
            for err in report.errors:
                print(f"    ERROR: {err.message}")

    if not all_passed:
        print("\n  ⚠ IronGate 校验失败，部分估值可能不可靠。继续执行...\n")

    # ── Step 2: DCF 估值 ───────────────────────────────────────────────
    print("\n[Step 2] DCF 估值计算...")
    dcf_engine = DCFEngine(DCF_EXAMPLE, skip_gates=True)
    dcf_result = dcf_engine.run()

    # 后置校验
    post_gates = dcf_engine.run_post_gates(dcf_result)
    print(f"  后置校验: {'PASS' if post_gates.passed else 'WARN'}")
    for r in post_gates.results:
        mark = "OK" if r.passed else "WARN" if r.severity == "warning" else "FAIL"
        print(f"    [{mark}] [{r.level}] {r.gate_id}: {r.message}")

    print(f"\n  基期营收:     {DCF_EXAMPLE.base_revenue:.0f} 亿元")
    print(f"  Year 5 营收:  {dcf_result.revenues[-1]:.0f} 亿元")
    print(f"  Year 5 FCF:   {dcf_result.fcf[-1]:.0f} 亿元")
    print(f"  PV of FCF:    {dcf_result.sum_pv_fcf:.0f} 亿元")
    print(f"  Terminal PV:  {dcf_result.terminal_value_pv:.0f} 亿元")
    print(f"  TV % of EV:   {dcf_result.tv_pct:.1%}")
    print(f"  Enterprise V: {dcf_result.enterprise_value:.0f} 亿元")
    print(f"  Equity Value: {dcf_result.equity_value:.0f} 亿元")
    print(f"  公允价值:     {dcf_result.fair_value_per_share:.2f} 元/股")
    if dcf_result.upside_pct is not None:
        print(f"  上行空间:     {dcf_result.upside_pct:+.1f}%")
    print(f"  置信度:       {dcf_result.confidence}")

    # ── Step 3: 可比估值 ───────────────────────────────────────────────
    print("\n[Step 3] 可比公司估值...")
    comp_engine = ComparableEngine(COMPARABLE_EXAMPLE, skip_gates=True)
    comp_result = comp_engine.run()

    print(f"  PE 隐含价格:  {comp_result.implied_prices.get('PE', 'N/A')}")
    print(f"  PB 隐含价格:  {comp_result.implied_prices.get('PB', 'N/A')}")
    print(f"  PS 隐含价格:  {comp_result.implied_prices.get('PS', 'N/A')}")
    print(f"  综合目标价:   {comp_result.target_price:.2f} 元/股")
    print(f"  置信度:       {comp_result.confidence}")

    # ── Step 4: 情景分析 ───────────────────────────────────────────────
    print("\n[Step 4] 情景分析...")
    scn_engine = ScenarioEngine(SCENARIO_EXAMPLE, skip_gates=True)
    scn_result = scn_engine.run()

    for name, price in scn_result.scenario_prices.items():
        prob = getattr(SCENARIO_EXAMPLE, name).probability
        print(f"  {name:>5}: {price:>8.2f} 元 (概率 {prob:.0%})")
    print(f"  加权目标:     {scn_result.weighted_target:.2f} 元/股")
    print(f"  上行:         {scn_result.upside_pct:+.1f}%")
    print(f"  下行:         {scn_result.downside_pct:+.1f}%")
    print(f"  风险收益比:   {scn_result.risk_reward:.2f}")

    # ── Step 5: SOTP 估值 ──────────────────────────────────────────────
    print("\n[Step 5] 分部加总 (SOTP) 估值...")
    sotp_engine = SOTPEngine(SOTP_EXAMPLE, skip_gates=True)
    sotp_result = sotp_engine.run()

    for seg in sotp_result.segment_values:
        print(f"  {seg['name']:>12}: {seg['method']:>8} × {seg['multiple']:>6.1f} = {seg['value']:>10.0f} 亿")
    print(f"  分部合计:     {sotp_result.total_segments_value:.0f} 亿元")
    print(f"  股权价值:     {sotp_result.equity_value:.0f} 亿元")
    print(f"  目标价:       {sotp_result.target_price:.2f} 元/股")
    if sotp_result.upside_pct is not None:
        print(f"  上行空间:     {sotp_result.upside_pct:+.1f}%")

    # ── Step 6: 导出 Excel 审计底稿 ────────────────────────────────────
    print("\n[Step 6] 导出 Excel 审计底稿...")
    writer = AuditExcelWriter(
        dcf_assumptions=DCF_EXAMPLE,
        comparable_assumptions=COMPARABLE_EXAMPLE,
        scenario_assumptions=SCENARIO_EXAMPLE,
        sotp_assumptions=SOTP_EXAMPLE,
    )
    outpath = writer.export("output/audit_valuation_model.xlsx")
    print(f"  成功生成: {outpath}")

    # ── Step 7: 汇总 ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  估值汇总")
    print("=" * 60)
    print(f"  DCF:         {dcf_result.fair_value_per_share:>8.2f} 元/股")
    print(f"  Comparable:  {comp_result.target_price:>8.2f} 元/股")
    print(f"  Scenario:    {scn_result.weighted_target:>8.2f} 元/股")
    print(f"  SOTP:        {sotp_result.target_price:>8.2f} 元/股")

    all_prices = [
        dcf_result.fair_value_per_share,
        comp_result.target_price,
        scn_result.weighted_target,
        sotp_result.target_price,
    ]
    avg = sum(all_prices) / len(all_prices)
    print("  ─────────────────────────")
    print(f"  综合均值:    {avg:>8.2f} 元/股")
    if DCF_EXAMPLE.current_price:
        upside = (avg / DCF_EXAMPLE.current_price - 1) * 100
        print(f"  vs 当前价:   {DCF_EXAMPLE.current_price:.0f} → {upside:+.1f}%")
    print()


if __name__ == "__main__":
    run_demo()
