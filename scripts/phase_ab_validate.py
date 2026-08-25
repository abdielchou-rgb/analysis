"""验证 Phase A+B 产出"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

print("=== Phase A: CLAUDE.md ===")
cl = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
if "FP0 优先级高于 FP1" in cl:
    print("  [OK] FP0>FP1 规则已写入")
else:
    print("  [FAIL] 规则未找到")

print("\n=== Phase B: 反向 DCF ===")
try:
    from core.compute.valuation.reverse_dcf import ReverseDCF

    rd = ReverseDCF(market_cap=150e8, net_debt=10e8, fcf_ttm=5e8, revenue_ttm=80e8, wacc=0.10, growth_assumption=5.0)
    r = rd.solve_implied_growth()
    print(f"  [OK] 隐含增长率={r.implied_growth_pct}%, 预期差={r.expectation_gap_pct}pp")
    print(f"  隐含FCF margin={r.implied_fcf_margin_pct}%")
    assert abs(r.implied_growth_pct - 3.23) < 0.1
    print("  [PASS] 反向DCF数值正确")
except Exception as e:
    print(f"  [FAIL] {e}")

print("\n=== Phase B: PEG ===")
try:
    from core.compute.valuation.peg import PEGValuation

    peg = PEGValuation(pe=25, growth_pct=20)
    r = peg.analyze()
    print(f"  [OK] PEG={r.peg_ratio}, 估值标签={r.valuation_label}")
    assert abs(r.peg_ratio - 1.25) < 0.01
    print("  [PASS] PEG数值正确")
except Exception as e:
    print(f"  [FAIL] {e}")

print("\n=== Phase B: Dupont ===")
try:
    from core.compute.financial.dupont import DupontAnalysis

    da = DupontAnalysis(net_profit=10, revenue=100, total_assets=200, equity=120)
    r = da.decompose()
    print(f"  [OK] ROE={r.roe_pct}% = 净利率{r.net_margin_pct}% x 周转率{r.asset_turnover} x 杠杆{r.equity_multiplier}")
    assert abs(r.roe_pct - 8.33) < 0.01
    print("  [PASS] Dupont数值正确")
except Exception as e:
    print(f"  [FAIL] {e}")

print("\n=== Phase A: gate_type_map ===")
import json

gtm = json.loads((ROOT / "config" / "gate_type_map.json").read_text(encoding="utf-8"))
print(f"  [OK] 5 报告类型，总计 {sum(len(v) for v in gtm.values())} 条配置")
for k in gtm:
    print(f"    {k}: {len(gtm[k])} 项")

print("\n=== DONE ===")
