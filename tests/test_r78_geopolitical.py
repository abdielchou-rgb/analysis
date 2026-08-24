"""R78 (2026-08-05) — 中美竞争/地缘政治引擎回归测试。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.geopolitical_engine import GeopoliticalEngine
from pipeline.iron_gate import IronGate


def test_engine_loads_events():
    """引擎应加载 geo_events.json。"""
    eng = GeopoliticalEngine()
    assert len(eng.events) >= 5, f"至少 5 条事件，实际 {len(eng.events)}"


def test_engine_filter_by_industry():
    """行业过滤应返回相关事件。"""
    eng = GeopoliticalEngine()
    semis = eng.filter_by_industry("半导体")
    assert len(semis) > 0, "半导体应有事件"
    # 每个事件应有 source（FP2）
    for ev in semis:
        assert ev.get("source"), f"事件缺 source: {ev.get('title')}"


def test_scenario_analysis():
    """双轨情景应输出概率 + 影响。"""
    eng = GeopoliticalEngine()
    r = eng.analyze("半导体")
    tracks = r["scenarios"]["tracks"]
    assert len(tracks) == 2
    total_prob = sum(t["probability"] for t in tracks)
    assert abs(total_prob - 1.0) < 0.01, f"概率应和为1: {total_prob}"


def test_exposure_metrics():
    """量化指标应输出暴露度/自主可控度。"""
    eng = GeopoliticalEngine()
    r = eng.analyze("半导体")
    exp = r["exposure"]
    assert "us_exposure" in exp and "self_controllability" in exp
    assert 0 <= exp["us_exposure"] <= 10


def test_build_injection():
    """注入块应含关键结构。"""
    eng = GeopoliticalEngine()
    r = eng.analyze("半导体")
    inj = eng.build_injection(r)
    assert "政策时间线" in inj or "双轨情景" in inj
    assert len(inj) > 100, f"注入块应足够长: {len(inj)}"


def test_gate_depth_distinguishes():
    """Gate 深度检查应区分浅层/深层。"""
    shallow = IronGate.__new__(IronGate)
    shallow.report_text = (
        "# 半导体报告\n公司2025年营收15.58亿元，毛利率44.8%，净利3.41亿元。"
        "行业成长期，竞争格局集中，国产替代推进，龙头受益。" * 20
    )
    r1 = shallow._check_geopolitical_depth()
    assert not r1.passed, "浅层（无事件）不应通过"

    deep = IronGate.__new__(IronGate)
    deep.report_text = (
        "# 半导体报告\n公司2025年营收15.58亿元，毛利率44.8%，净利3.41亿元。"
        "2024年12月美国BIS实体清单升级，出口管制对AI芯片冲击显著，"
        "国产替代加速，自主可控度提升至4.8/10，脱钩概率85%，受益标的明确。" * 18
    )
    r2 = deep._check_geopolitical_depth()
    assert r2.passed, "深层（有事件+量化+传导）应通过"


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
