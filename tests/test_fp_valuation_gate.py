"""FP v3.2 (2026-08-03) 回归测试 — 估值规则全量接线 + Gate 回测基线校准。

FP-4：valuation_deep 规则接入 comparable/scenario（不只 DCF）。
FP-5：Gate min_chars 按回测金牌 p10 校准。
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── FP-4: 估值护栏全量 ─────────────────────────────
def test_comparable_guard_few_peers():
    """可比公司 <3 家应提示可比性不足。"""
    from core.compute.valuation_guardrails import validate_comparable_guards
    issues = validate_comparable_guards(target_pe=22, implied_price=25, peer_count=2, company_eps=1.2)
    assert any("可比公司仅" in i for i in issues), f"可比<3应提示: {issues}"


def test_comparable_guard_ok():
    """可比公司 ≥3 家应通过。"""
    from core.compute.valuation_guardrails import validate_comparable_guards
    assert validate_comparable_guards(target_pe=22, implied_price=25, peer_count=5, company_eps=1.2) == []


def test_scenario_guard_monotonicity():
    """情景 bull<base<bear 倒挂应拦截。"""
    from core.compute.valuation_guardrails import validate_scenario_guards
    issues = validate_scenario_guards(bull=30, base=28, bear=35, risk_reward=1.5)
    assert any("情景排序" in i for i in issues), f"倒挂应拦截: {issues}"


def test_scenario_guard_extreme():
    """乐观/悲观价差 >3 倍应提示。"""
    from core.compute.valuation_guardrails import validate_scenario_guards
    issues = validate_scenario_guards(bull=80, base=30, bear=20, risk_reward=1.5)
    assert any("价差过大" in i for i in issues), f"极差应提示: {issues}"


def test_compute_engine_wires_all():
    """compute_engine 应接线可比+情景护栏（不只 DCF）。"""
    src = (_ROOT / "pipeline" / "compute_engine.py").read_text(encoding="utf-8")
    assert "validate_comparable_guards" in src, "应接线可比护栏"
    assert "validate_scenario_guards" in src, "应接线情景护栏"
    assert "validate_dcf_guards" in src, "应保留DCF护栏"


# ── FP-5: Gate 回测基线校准 ───────────────────────
def test_min_chars_calibrated():
    """min_chars 应按回测金牌 p10 校准（10420）。"""
    from pipeline.iron_gate import IronGate
    gate = IronGate.from_text("x" * 500, report_type="industry_deep", style="cicc")
    assert gate.min_chars == 10420, f"industry min_chars应=10420: {gate.min_chars}"


def test_judgment_density_uses_backtest():
    """judgment_density 阈值应由 backtest_deep 推导。"""
    import json
    d = json.loads((_ROOT / "data" / "methodology_backtest_deep.json").read_text(encoding="utf-8"))
    gr = d.get("gate_reference", {})
    assert gr.get("min_judgment_density") == 1.2, "backtest p10 判断密度应=1.2"
    assert gr.get("min_data_density") == 5.0, "backtest p10 数据密度应=5.0"
    # IronGate 默认阈值应对齐
    from pipeline.iron_gate import IronGate
    gate = IronGate.from_text("x" * 500, report_type="industry_deep", style="cicc")
    # R63（2026-08-04）：R61 迁移后阈值常量移至 checks/content_format_mixin.py，
    # 原断言查 iron_gate.py 源码已失配。改为查 mixin 实现文件。
    src = (_ROOT / "pipeline" / "checks" / "content_format_mixin.py").read_text(encoding="utf-8")
    assert 'MIN_JUDGMENT_DENSITY", "1.2"' in src, "判断密度默认应1.2"
    assert 'MIN_DATA_DENSITY", "5.0"' in src, "数据密度默认应5.0"


if __name__ == "__main__":
    import traceback
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
