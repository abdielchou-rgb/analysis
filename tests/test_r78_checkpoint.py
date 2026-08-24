"""R78 (2026-08-05) — 写改循环 checkpoint 回归测试。"""
import os, sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.write_checkpoint import save_checkpoint, load_checkpoint, clear_checkpoint


def test_checkpoint_roundtrip():
    """保存→读取→清除 全流程。"""
    save_checkpoint("__ck_test__", "industry_deep", {"attempt": 2, "report_text": "文本", "gate_feedback": "x"})
    ck = load_checkpoint("__ck_test__")
    assert ck is not None and ck["attempt"] == 2
    assert ck["report_text"] == "文本"
    assert clear_checkpoint("__ck_test__") is True
    assert load_checkpoint("__ck_test__") is None


def test_checkpoint_missing_returns_none():
    """不存在的 checkpoint 返回 None。"""
    assert load_checkpoint("__no_such_asset__") is None


def test_e2e_has_checkpoint_code():
    """e2e 应含 checkpoint 保存/恢复/清除接线。"""
    src = (_ROOT / "pipeline" / "e2e_orchestrator.py").read_text(encoding="utf-8")
    assert "save_checkpoint" in src
    assert "load_checkpoint" in src
    assert "clear_checkpoint" in src


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
