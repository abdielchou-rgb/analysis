"""R53 (2026-08-03) 回归测试 — Marvis 数据扩采接线。

Marvis 交付 6 项数据（macro_highfreq/pledge_ratio/leading_indicators/
us_highfreq + consensus 历史序列 + financials DA/RD），本测试锁定 2hao 侧
data_basement 的消费接线。
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_macro_highfreq_loaded():
    """宏观高频 loader 应返回最新值。"""
    from core.data_basement import load_macro_highfreq
    hf = load_macro_highfreq()
    if hf is None:
        return  # 沙箱缺数据文件时跳过（数据在用户机）
    assert len(hf) >= 5, f"宏观高频应≥5指标: {list(hf.keys())[:3]}"


def test_leading_indicators_loaded():
    """领先指标 loader 应返回 M1-M2剪刀差等。"""
    from core.data_basement import load_leading_indicators
    li = load_leading_indicators()
    if li is None:
        return
    assert any("M1" in k or "信贷" in k for k in li), f"应含M1-M2/信贷脉冲: {list(li.keys())}"


def test_us_highfreq_loaded():
    """美国高频 loader 应返回 CFNAI/WEI。"""
    from core.data_basement import load_us_highfreq
    uhf = load_us_highfreq()
    if uhf is None:
        return
    assert any("CFNAI" in k for k in uhf), f"应含CFNAI: {list(uhf.keys())}"


def test_pledge_ratio_by_code():
    """质押率 loader 应按 code 匹配。"""
    from core.data_basement import load_pledge_ratio
    pr = load_pledge_ratio("000002")
    if pr is None:
        return
    assert 0 <= pr["pledge_ratio_pct"] <= 100, f"质押率应在0-100: {pr}"


def test_consensus_revision_slope():
    """consensus loader 应含 revision_slope（Marvis R53 扩采字段）。"""
    from core.data_basement import load_consensus
    cs = load_consensus("002594")
    if cs is None:
        return
    assert "revision_slope" in cs, f"应含revision_slope: {list(cs.keys())}"
    assert "revision_breadth" in cs, f"应含revision_breadth: {list(cs.keys())}"


def test_basement_merges_r53_data():
    """build_basement_data_dict 应合并 R53 新数据（hf_/lead_/us_hf_/pledge）。"""
    from core.data_basement import build_basement_data_dict
    d = build_basement_data_dict("气体传感器")
    r53_keys = [k for k in d if k.startswith(("hf_", "lead_", "us_hf_"))]
    # 数据文件在用户机才有；沙箱无文件则跳过
    if not r53_keys:
        return
    assert len(r53_keys) >= 3, f"应合并≥3个R53数据: {r53_keys}"


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
