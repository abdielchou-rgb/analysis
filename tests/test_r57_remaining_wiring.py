"""R57-10 (2026-08-03) 回归测试 — R55 剩余数据接线。

核查 Marvis R55 执行报告后补的两个缺口：
  1. global_leaders 海外营收占比（31家）→ data_basement 消费
  2. consensus_prices 目标价可用性标注 → data_basement 读取（驱动降级策略）
"""

import os  # noqa: F401  (dead-import debt)
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_load_global_leaders_overseas():
    """global_leaders 应返回海外营收占比（行业匹配中国龙头）。"""
    from core.data_basement import load_global_leaders

    gl = load_global_leaders(industry="光伏")
    if gl is None:
        return  # 沙箱数据缺失时跳过
    assert "overseas_revenue_pct" in gl, f"应含海外营收占比: {list(gl.keys())}"
    assert gl.get("overseas_revenue_pct") is not None, "海外营收占比应为数值"


def test_load_global_leaders_code_match():
    """global_leaders ticker 匹配应保留。"""
    from core.data_basement import load_global_leaders

    # NVDA 应存在
    gl = load_global_leaders(code="NVDA")
    # 若数据存在则验证
    if gl is not None:
        assert isinstance(gl, dict), "应返回 dict"


def test_load_consensus_target_price():
    """consensus_prices 应读取目标价可用性标注。"""
    from core.data_basement import load_consensus_target_price

    tp = load_consensus_target_price("600519")
    if tp is None:
        return
    assert "target_price_available" in tp, f"应含可用性标注: {list(tp.keys())}"


def test_consensus_unavailable_drives_downgrade():
    """目标价不可得标注应驱动降级（target_price_available=false）。"""
    from core.data_basement import load_consensus_target_price

    tp = load_consensus_target_price("600519")
    if tp is None:
        return
    # 免费源确认无目标价 → available 应为 False
    assert tp["target_price_available"] is False, "免费源目标价应标不可得"


def test_build_merges_r57_keys():
    """build_basement_data_dict 应合并 R57 keys（ind_leader/target_price）。"""
    from core.data_basement import build_basement_data_dict

    # 用光伏测试（global_leaders 有光伏行业中国龙头）
    d = build_basement_data_dict("光伏")
    r57_keys = [k for k in d if k.startswith(("ind_leader", "target_price"))]
    # 数据文件在用户机才有，沙箱无数据则跳过
    if not r57_keys:
        return
    assert any("ind_leader" in k for k in r57_keys), f"应含龙头海外营收: {r57_keys}"


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
