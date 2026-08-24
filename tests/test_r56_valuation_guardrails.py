"""R56 (2026-08-03) 回归测试 — 估值规则接线 compute。

把 methodology_valuation_deep.json 的可执行估值规则落地为
DCF 计算后的确定性校验（valuation_guardrails.py）。
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_g_less_than_r():
    """永续增长 g < 折现率 r 应通过；g >= r 应拦截。"""
    from core.compute.valuation_guardrails import validate_dcf_guards
    assert validate_dcf_guards(wacc=0.10, terminal_growth=0.03, tv_pct=0.5, fair_value=48) == []
    issues = validate_dcf_guards(wacc=0.10, terminal_growth=0.12, tv_pct=0.5, fair_value=48)
    assert any("g=" in i and "≥" in i for i in issues), f"g>=r应拦截: {issues}"


def test_terminal_value_pct():
    """终值占比 >80% 应拦截。"""
    from core.compute.valuation_guardrails import validate_dcf_guards
    issues = validate_dcf_guards(wacc=0.10, terminal_growth=0.03, tv_pct=0.88, fair_value=48)
    assert any("终值占比" in i for i in issues), f"终值过高应拦截: {issues}"


def test_fair_value_positive():
    """fair_value <= 0 应拦截。"""
    from core.compute.valuation_guardrails import validate_dcf_guards
    issues = validate_dcf_guards(fair_value=-1, wacc=0.1, terminal_growth=0.03)
    assert any("公允价值" in i for i in issues), f"负值应拦截: {issues}"


def test_multi_method_consistency():
    """多方法差异 >30% 应提示定位分歧根因。"""
    from core.compute.valuation_guardrails import check_multi_method_consistency
    assert check_multi_method_consistency({"dcf": 48, "pe": 46, "comparable": 50}) == []
    issues = check_multi_method_consistency({"dcf": 48, "pe": 44, "comparable": 70})
    assert any("分歧根因" in i for i in issues), f"差异应提示: {issues}"


def test_rules_loaded_from_kb():
    """规则应来自知识库 methodology_valuation_deep.json。"""
    import json
    p = _ROOT / "data" / "methodology_valuation_deep.json"
    assert p.exists(), "估值知识库缺失"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert "dcf" in d and "checklist" in d["dcf"], "估值知识库应含DCF规则"


def test_compute_engine_wires_guardrails():
    """compute_engine._run_v51_dcf 应接线估值护栏。"""
    src = (_ROOT / "pipeline" / "compute_engine.py").read_text(encoding="utf-8")
    assert "valuation_guardrails" in src, "compute_engine 应引用估值护栏"
    assert "guardrail_issues" in src, "DCF 结果应含 guardrail_issues 字段"


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
