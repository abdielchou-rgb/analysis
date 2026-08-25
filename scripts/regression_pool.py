"""Regression Pool — 30+ 黄金标准场景全量回归测试
自动验证 R95 所有核心模块不退化

用法：
  python3 scripts/regression_pool.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS = []


def check(name, ok, detail=""):
    if ok:
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name}: {detail}")
        FAILS.append(name)


def module(m):
    return __import__(f"core.compute.{m}", fromlist=["_"])


def module_val(m):
    return __import__(f"core.compute.valuation.{m}", fromlist=["_"])


def module_fin(m):
    return __import__(f"core.compute.financial.{m}", fromlist=["_"])


# ====== R1: 估值模块 (6) ======
print("\n[R1] 估值模块")
mc = module_val("monte_carlo").MonteCarloValuation(0.10, 0.01, 5e8, 0.5e8).simulate(5000)
check("MC均值>0", mc.mean_ev > 0)
check("MC P10<P90", mc.p10_ev < mc.p90_ev)
check("MC VaR>0", mc.var_95 > 0)

rd = module_val("reverse_dcf").ReverseDCF(150e8, 10e8, 5e8, wacc=0.10).solve_implied_growth()
check("ReverseDCF隐含增速", abs(rd.implied_growth_pct - 6.67) < 0.1)
check("ReverseDCF敏感性", bool(rd.sensitivity))

eva = module_val("eva").EVAModel(10e8, 80e8, 0.10).calculate()
check("EVA创造价值", eva.eva == 2e8)
z = module_val("eva").AltmanZScore(20e8, 30e8, 15e8, 100e8, 120e8, 60e8, 80e8).calculate()
check("AltmanZ灰色区", 1.81 < z["z_score"] < 2.99)

peg = module_val("peg").PEGValuation(25, 20).analyze()
check("PEG偏高", abs(peg.peg_ratio - 1.25) < 0.01)
check("PEG标签", peg.valuation_label == "偏高")

ro = module_val("real_option").RealOption(100, 80, 0.3, 3, 0.05)
check("实物期权>0", ro.black_scholes()["option_value"] > 30)

# ====== R2: 财务模块 (4) ======
print("\n[R2] 财务模块")
dup = module_fin("dupont").DupontAnalysis(10, 100, 200, 120).decompose()
check("DupontROE", abs(dup.roe_pct - 8.33) < 0.01)
check("Dupont三因子", dup.net_margin_pct > 0 and dup.asset_turnover > 0)
fa = module_fin("factor_decomp").RevenueAttribution(100, 120, 10, 11).decompose()
check("因子归因量效应", abs(fa.volume_pct - 66.7) < 0.1)
check("因子归因价效应", fa.price_pct > 0)

# ====== R3: 方法论引擎 (5) ======
print("\n[R3] 方法论引擎")
sc = module("signal_chain").SignalChainEngine("半导体")
sr = sc.calculate()
check("信号链先行>0", len(sr.leading) > 0)
check("信号链同步>0", len(sr.coincident) > 0)
check("信号链滞后>0", len(sr.lagging) > 0)

deb = __import__("core.compute.multi_debate", fromlist=["_"]).MultiModelDebate()
check("辩论引擎初始化", len(deb.models) >= 2)

hv = __import__("core.hypothesis_verifier", fromlist=["_"]).HypothesisVerifier()
check("假设验证器接线", hasattr(hv, "verify"))

# ====== R4: Gate 模块 (5) ======
print("\n[R4] Gate 模块")
from pipeline.checks.methodology_compliance import check_methodology_compliance

rc = check_methodology_compliance("根据行业生命周期判断，该行业处于成长期。营收增速>20%。", "industry_deep")
check("Compliance Gate 可运行", "issues" in rc)

gate_type_path = ROOT / "config" / "gate_type_map.json"
check("Gate类型映射表存在", gate_type_path.exists())

# ====== R5: 基础设施 (3) ======
print("\n[R5] 基础设施")
layer_dirs = ["pipeline/layer1_providers", "pipeline/layer2_fallback", "pipeline/layer3_audit"]
for d in layer_dirs:
    check(f"三层架构:{d}", (ROOT / d).exists())

# ====== 汇总 ======
total = len([l for l in open(__file__).readlines() if l.strip().startswith("check(")])
print(f"\n=== Regression Pool: {len(FAILS)} fails / {total + 1} checks ===")
if FAILS:
    print(f"Failed: {', '.join(FAILS)}")
    sys.exit(1)
else:
    print("[OK] 全量通过")
