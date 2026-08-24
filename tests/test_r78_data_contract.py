"""R78 (2026-08-05) — 数据契约校验回归测试。"""
import os, sys, json, tempfile
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_contract import validate_enrich_file, validate_enrich_item, validate_chart_data


def test_valid_enrich_item():
    ok, reason = validate_enrich_item(
        {"type": "fig_data", "key": "fig_revenue_trend", "data": {"2024": 50}, "source": "测试"})
    assert ok, reason


def test_missing_source_rejected():
    ok, reason = validate_enrich_item(
        {"type": "fig_data", "key": "fig_revenue_trend", "data": {"2024": 50}, "source": ""})
    assert not ok, "缺 source 应拒绝"
    assert "source" in reason


def test_unknown_key_rejected():
    ok, reason = validate_enrich_item(
        {"type": "fig_data", "key": "fig_not_real", "data": {"x": 1}, "source": "s"})
    assert not ok, "白名单外 key 应拒绝"


def test_empty_data_rejected():
    ok, reason = validate_enrich_item(
        {"type": "fig_data", "key": "fig_revenue_trend", "data": {}, "source": "s"})
    assert not ok, "空 data 应拒绝"


def test_chart_data_contract():
    ok, problems = validate_chart_data({"fig_revenue_trend": {"2024": 50}, "company_intro": "文本"})
    assert ok, problems
    ok2, p2 = validate_chart_data({"fig_revenue_trend": "not_a_dict"})
    assert not ok2, "fig_revenue_trend 应为 dict"


if __name__ == "__main__":
    import traceback
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"  OK {name}"); passed += 1
            except Exception as e:
                print(f"  FAIL {name}: {e}"); traceback.print_exc(); failed += 1
    print(f"\n{passed} passed, {failed} failed")
