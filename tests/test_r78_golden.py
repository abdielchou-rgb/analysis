"""R78 (2026-08-05) — golden dataset 回归测试。

对 tests/golden/*.md 样本做确定性断言（篇幅/结构/判断密度/数据密度/反方论证/无AI免责）。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = _ROOT / "tests" / "golden"
sys.path.insert(0, str(GOLDEN_DIR))

from golden_check import check_one


def test_golden_samples_exist():
    """golden 目录应有样本。"""
    samples = list(GOLDEN_DIR.glob("*.md"))
    assert len(samples) >= 2, f"至少 2 份 golden 样本，实际 {len(samples)}"


def test_all_golden_pass():
    """全部 golden 样本应通过确定性断言。"""
    samples = sorted(GOLDEN_DIR.glob("*.md"))
    assert samples, "无 golden 样本"
    for f in samples:
        r = check_one(f)
        assert all(r["results"].values()), f"{f.name} 未通过: {r['results']}"


def test_golden_no_ai_disclaimer():
    """golden 样本不应含 AI 免责声明（R42/R72 合规）。"""
    for f in GOLDEN_DIR.glob("*.md"):
        r = check_one(f)
        assert r["metrics"]["no_ai_disclaimer"], f"{f.name} 含 AI 免责声明"


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
