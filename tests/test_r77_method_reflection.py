"""R77 (2026-08-05) 回归测试 — P0-3 方法选择数据驱动初代。

1. record_reflection 首次实测覆盖估算基线（不污染滑动平均）
2. 后续实测滑动平均
3. e2e 出口已接线 record_reflection（报告完成自动记录）
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_registry():
    return json.loads((_ROOT / "data" / "framework_registry.json").read_text(encoding="utf-8"))


def test_estimate_marked_in_registry():
    """registry 效果字段应带"估算基线"标记（R77 打标）。"""
    d = _load_registry()
    for fw in d["frameworks"]:
        eff = fw.get("效果", {})
        assert "数据来源" in eff, f"{fw['id']} 效果字段应有数据来源标记"
        assert "估算" in eff.get("数据来源", ""), f"{fw['id']} 应为估算标记"


def test_first_real_record_overrides_estimate():
    """首次实测记录应覆盖估算，不混入滑动平均。"""
    from core.method_reflection import record_reflection

    reg = _ROOT / "data" / "framework_registry.json"
    backup = reg.read_text(encoding="utf-8")
    try:
        record_reflection(
            asset="__r77test__",
            report_type="industry_deep",
            frameworks=["signal_chain"],
            gate_score=0.77,
            data_sufficiency={"sufficient": True},
        )
        d = _load_registry()
        for fw in d["frameworks"]:
            if fw["id"] == "signal_chain":
                eff = fw["效果"]
                assert eff["已用次数"] == 1, f"首次实测应重置次数: {eff}"
                assert eff["平均Gate分"] == 0.77, f"首次实测应覆盖估算: {eff}"
                assert "实测" in eff.get("数据来源", ""), f"应标记实测: {eff}"
    finally:
        reg.write_text(backup, encoding="utf-8")


def test_second_record_sliding_average():
    """后续实测应滑动平均。"""
    from core.method_reflection import record_reflection

    reg = _ROOT / "data" / "framework_registry.json"
    backup = reg.read_text(encoding="utf-8")
    try:
        # 先设实测基线
        record_reflection(
            asset="__r77a__",
            report_type="industry_deep",
            frameworks=["signal_chain"],
            gate_score=0.80,
            data_sufficiency={"sufficient": True},
        )
        record_reflection(
            asset="__r77b__",
            report_type="industry_deep",
            frameworks=["signal_chain"],
            gate_score=0.90,
            data_sufficiency={"sufficient": True},
        )
        d = _load_registry()
        for fw in d["frameworks"]:
            if fw["id"] == "signal_chain":
                eff = fw["效果"]
                assert eff["已用次数"] == 2, f"应累计2次: {eff}"
                assert abs(eff["平均Gate分"] - 0.85) < 0.001, f"应滑动平均: {eff}"
    finally:
        reg.write_text(backup, encoding="utf-8")


def test_e2e_record_results_wired():
    """e2e record_results 应含 record_reflection 接线。"""
    src = (_ROOT / "pipeline" / "e2e_orchestrator.py").read_text(encoding="utf-8")
    assert "record_reflection" in src, "e2e 出口应接线 record_reflection"
    assert "e2e 出口自动记录" in src, "应注释标记 e2e 出口自动记录"


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  OK {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
