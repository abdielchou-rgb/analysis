import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

n = 0
tests = []

def run(name, fn):
    global n
    try:
        fn()
        print(f"  [{name}] PASS")
        n += 1
    except Exception as e:
        print(f"  [{name}] FAIL: {e}")

core = lambda m: __import__(f"core.{m}", fromlist=["_"])
pipe = lambda m: __import__(f"pipeline.{m}", fromlist=["_"])

run("RealOption", lambda: core("compute.valuation.real_option").RealOption(100,80,0.3,3,0.05).black_scholes()["option_value"] > 0)
run("MonteCarlo", lambda: core("compute.valuation.monte_carlo").MonteCarloValuation(0.10,0.01,5e8,0.5e8).simulate(5000).mean_ev > 0)
run("EVA", lambda: core("compute.valuation.eva").EVAModel(10e8,80e8,0.10).calculate().eva == 2e8)
run("AltmanZ", lambda: 1.81 < core("compute.valuation.eva").AltmanZScore(20e8,30e8,15e8,100e8,120e8,60e8,80e8).calculate()["z_score"] < 2.99)
run("ReverseDCF", lambda: abs(core("compute.valuation.reverse_dcf").ReverseDCF(150e8,10e8,5e8,wacc=0.10).solve_implied_growth().implied_growth_pct - 6.67) < 0.1)
run("PEG", lambda: abs(core("compute.valuation.peg").PEGValuation(25,20).analyze().peg_ratio - 1.25) < 0.01)
run("Dupont", lambda: abs(core("compute.financial.dupont").DupontAnalysis(10,100,200,120).decompose().roe_pct - 8.33) < 0.01)
run("FactorAttr", lambda: abs(core("compute.financial.factor_decomp").RevenueAttribution(100,120,10,11).decompose().volume_pct - 66.7) < 0.1)
run("FP5", lambda: "FP5" in pipe("fp5_feedback").FP5FeedbackLoop().get_stats())

print(f"\n=== Phase F+H 全量验证: {n}/9 ===")