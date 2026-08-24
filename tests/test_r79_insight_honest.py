"""R79 P1 — 洞察质量 + 诚实留白 + 三角验证回归测试。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_insight_rejects_cliche():
    """常识复述判断应降分。"""
    from pipeline.iron_gate import IronGate

    ig = IronGate.__new__(IronGate)
    ig.report_text = "我们判断行业受益于政策。我们认为需求将持续增长。预计市场格局优化。我们判断国产替代加速。" * 12
    r = ig._check_insight_quality()
    assert not r.passed, "常识复述应降分"
    assert "常识复述" in r.details


def test_insight_passes_anchored():
    """有锚点判断应通过。"""
    from pipeline.iron_gate import IronGate

    ig = IronGate.__new__(IronGate)
    ig.report_text = (
        "我们判断2026H2加油站防渗改造执行率62%→85%将触发替换高峰。我们认为磁致伸缩良率92%突破是国产替代拐点。" * 10
    )
    r = ig._check_insight_quality()
    assert r.passed, f"有锚点判断应通过: {r.details}"


def test_honest_gap_rewards_declaration():
    """留白声明应加分。"""
    from pipeline.iron_gate import IronGate

    ig = IronGate.__new__(IronGate)
    ig.report_text = "船舶细分市场规模数据不足，明确留白（无权威数据源）。行业增速8.7%(A)，国产替代加速。" * 5
    r = ig._check_honest_gap()
    assert r.passed and r.severity == "info", f"留白应加分: {r.details}"


def test_honest_gap_penalizes_fabrication():
    """无来源硬凑数字应降分。"""
    from pipeline.iron_gate import IronGate

    ig = IronGate.__new__(IronGate)
    ig.report_text = "船舶细分市场规模24.7亿元，增速15.3%，渗透率8.2%。另一细分市场规模31.5亿元，增速9.1%。" * 3
    r = ig._check_honest_gap()
    assert not r.passed, "硬凑数字应降分"


def test_triangulation_consistent():
    """三法一致应通过。"""
    from core.triangulation import triangulate

    r = triangulate(
        [
            {"method": "自上而下", "value": 50, "basis": "A"},
            {"method": "自下而上", "value": 52, "basis": "B"},
            {"method": "对标", "value": 47, "basis": "C"},
        ]
    )
    assert r.consistent, f"偏差10%应一致: {r.spread_pct:.0%}"
    assert 45 < r.midpoint < 55


def test_triangulation_inconsistent():
    """三法矛盾应报不一致。"""
    from core.triangulation import triangulate

    r = triangulate(
        [
            {"method": "A", "value": 32, "basis": "窄口径"},
            {"method": "B", "value": 50, "basis": "全口径"},
        ]
    )
    assert not r.consistent, "偏差大应不一致"
    assert "口径" in r.note, "应提示核查口径"


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
