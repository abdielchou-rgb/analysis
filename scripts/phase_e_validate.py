"""全量验证 Phase E 新模块"""
import sys
sys.path.insert(0, ".")

print("=== Phase E: 新计算模块全量验证 ===\n")

n = 0

# 1 Monte Carlo
try:
    from core.compute.valuation.monte_carlo import MonteCarloValuation
    mc = MonteCarloValuation(0.10, 0.01, 5e8, 0.5e8)
    r = mc.simulate(5000)
    assert r.mean_ev > 0
    print(f"[MC]  均值={r.mean_ev:.0f} P10={r.p10_ev:.0f} P90={r.p90_ev:.0f}  PASS")
    n += 1
except Exception as e:
    print(f"[MC]  FAIL: {e}")

# 2 EVA
try:
    from core.compute.valuation.eva import EVAModel, AltmanZScore
    eva = EVAModel(nopat=10e8, invested_capital=80e8, wacc=0.10)
    er = eva.calculate()
    assert er.eva == 2e8
    print(f"[EVA] EVA={er.eva:.0f} 判定={er.verdict}  PASS")
    n += 1
except Exception as e:
    print(f"[EVA]  FAIL: {e}")

# 3 Altman Z
try:
    az = AltmanZScore(20e8, 30e8, 15e8, 100e8, 120e8, 60e8, 80e8)
    azr = az.calculate()
    assert azr["z_score"] > 2.99
    print(f"[AltmanZ] Z={azr['z_score']} 判定={azr['zone'][:6]}  PASS")
    n += 1
except Exception as e:
    print(f"[AltmanZ]  FAIL: {e}")

# 4 Reverse DCF
try:
    from core.compute.valuation.reverse_dcf import ReverseDCF
    rd = ReverseDCF(150e8, 10e8, 5e8, wacc=0.10)
    rr = rd.solve_implied_growth()
    assert abs(rr.implied_growth_pct - 6.67) < 0.1
    print(f"[ReverseDCF] 隐含增速={rr.implied_growth_pct}% 预期差={rr.expectation_gap_pct}pp  PASS")
    n += 1
except Exception as e:
    print(f"[ReverseDCF]  FAIL: {e}")

# 5 PEG
try:
    from core.compute.valuation.peg import PEGValuation
    peg = PEGValuation(25, 20)
    pr = peg.analyze()
    assert abs(pr.peg_ratio - 1.25) < 0.01
    print(f"[PEG]  ratio={pr.peg_ratio} 判定={pr.valuation_label}  PASS")
    n += 1
except Exception as e:
    print(f"[PEG]  FAIL: {e}")

# 6 Dupont
try:
    from core.compute.financial.dupont import DupontAnalysis
    da = DupontAnalysis(10, 100, 200, 120)
    dr = da.decompose()
    assert abs(dr.roe_pct - 8.33) < 0.01
    print(f"[Dupont] ROE={dr.roe_pct}% = {dr.net_margin_pct}% x {dr.asset_turnover} x {dr.equity_multiplier}  PASS")
    n += 1
except Exception as e:
    print(f"[Dupont]  FAIL: {e}")

print(f"\n=== 全量验证通过: {n}/6 ===")
if n == 6:
    print("[RESULT] 全部通过，Phase E 交付完成")
else:
    print(f"[RESULT] {6-n} 项未通过，需排查")