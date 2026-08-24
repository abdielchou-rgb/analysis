"""R54 (2026-08-03) 回归测试 — 训练模式收敛判定。

P2-8 遗留：train_loop 有失败项变化检测但无"分数平稳=收敛"显式判定。
修复：is_converged() 辅助函数——连续 streak 轮分数变化 < eps → 收敛。
"""

import os  # noqa: F401  (dead-import debt)
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_converged_flat_scores():
    """分数完全平稳 → 收敛。"""
    from scripts.train_loop import is_converged

    assert is_converged([0.85, 0.85, 0.85])
    assert is_converged([0.90, 0.9005, 0.9001])  # 变化<0.01


def test_converged_small_variation():
    """分数小幅波动（<eps）→ 收敛。"""
    from scripts.train_loop import is_converged

    assert is_converged([0.84, 0.848, 0.841])  # spread 0.008 < 0.01


def test_not_converged_improving():
    """分数持续上升 → 未收敛（继续重跑有价值）。"""
    from scripts.train_loop import is_converged

    assert not is_converged([0.80, 0.85, 0.90])


def test_not_converged_insufficient():
    """不足 streak 轮 → 未收敛。"""
    from scripts.train_loop import is_converged

    assert not is_converged([0.85, 0.86])
    assert not is_converged([])


def test_not_converged_dropping():
    """分数骤降 → 未收敛（可能有回归，需继续）。"""
    from scripts.train_loop import is_converged

    assert not is_converged([0.90, 0.92, 0.85])


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
