"""R77 (2026-08-05) 回归测试 — P0-2 覆盖意识 staleness detection。

覆盖检查从 checklist 升级为 staleness detection：
1. universe_build 输出 data_freshness（数据底座时效性）
2. IronGate warning 级行业底座缺口检查（不阻断）
3. _COVERAGE_ENRICH_THRESHOLD 从 framework_registry.json 读（FP5 校准口子）
4. agent_provider 队列积压快速失败（防 IronGate 挂死）
"""

import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

for line in (_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)


def test_universe_build_has_data_freshness():
    """build() 输出应含 data_freshness。"""
    from pipeline.universe_build import UniverseBuilder

    b = UniverseBuilder()
    r = b.build("人形机器人", {"chart_data": {"company_intro": "机器人产业"}}, "industry_deep")
    s = r["universe_summary"]
    assert "data_freshness" in s, f"build 应输出 data_freshness: {list(s.keys())}"
    df = s["data_freshness"]
    assert "unlisted_players" in df and "brand_entity_mapping" in df
    for source, info in df.items():
        assert "age_days" in info and "stale" in info and "recommend_action" in info


def test_staleness_check_reports_stale():
    """超过 _STALE_DAYS 的底座应标记 stale_refresh。"""
    import pipeline.universe_build as ub

    b = ub.UniverseBuilder()
    b._data_mtime = {
        "unlisted_players": time.time() - 100 * 86400,
        "brand_entity_mapping": time.time() - 100 * 86400,
    }
    r = b.staleness_check()
    for source, info in r.items():
        assert info["stale"] is True, f"{source} 应标记 stale"
        assert info["recommend_action"] == "stale_refresh"


def test_industry_baseline_gap_warning():
    """IronGate 行业底座缺口应为 warning 级、不阻断。"""
    from pipeline.iron_gate import IronGate

    text = "未知板块行业分析。\n公司2025年营收15.58亿元，毛利率44.8%。\n" * 3
    ig = IronGate.__new__(IronGate)
    ig.report_text = text
    ig.asset = "未知标的"
    r = ig._check_industry_baseline_gap()
    assert r.passed is True, "行业缺口检查不应阻断报告"
    assert r.severity == "warning", f"应为 warning 级: {r.severity}"


def test_industry_baseline_ok_for_known_sector():
    """底座已覆盖的行业不应误报缺口。"""
    from pipeline.iron_gate import IronGate

    text = "传感器行业分析。\n公司2025年营收15.58亿元，毛利率44.8%。\n" * 3
    ig = IronGate.__new__(IronGate)
    ig.report_text = text
    ig.asset = "油位传感器"
    r = ig._check_industry_baseline_gap()
    assert "缺口" not in r.details, f"不应误报缺口: {r.details}"


def test_coverage_threshold_from_registry():
    """_COVERAGE_ENRICH_THRESHOLD 应从 registry 读。"""
    import json

    from pipeline.universe_build import _COVERAGE_ENRICH_THRESHOLD

    reg = json.loads((_ROOT / "data" / "framework_registry.json").read_text(encoding="utf-8"))
    calib = reg.get("_meta", {}).get("calibration", {})
    expected = float(calib.get("coverage_enrich_threshold", 0.7))
    assert _COVERAGE_ENRICH_THRESHOLD == expected, f"阈值应从 registry 读: {_COVERAGE_ENRICH_THRESHOLD} != {expected}"


def test_agent_provider_fast_fail_no_heartbeat():
    """agent_provider 无活跃 responder（无心跳）时应快速失败，不空等 300s。"""

    from core.agent_provider import QUEUE_DIR, AgentProvider

    # 确保无心跳文件
    hb = QUEUE_DIR / ".heartbeat"
    hb_was = hb.exists()
    if hb_was:
        hb_backup = hb.read_text(encoding="utf-8")
        hb.unlink()
    try:
        ap = AgentProvider()
        t0 = time.time()
        try:
            ap.__call__([{"role": "user", "content": "hi"}])
            assert False, "无 responder 不应调用成功"
        except RuntimeError as e:
            elapsed = time.time() - t0
            assert "不在线" in str(e), f"应报 responder 不在线: {e}"
            assert elapsed < 10, f"应快速失败, 实际 {elapsed:.1f}s"
    finally:
        if hb_was:
            hb.write_text(hb_backup, encoding="utf-8")


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
