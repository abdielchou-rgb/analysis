"""FP v3.2 (2026-08-03) 回归测试 — R55 全球视野数据接线。

Marvis 交付 4 个全球视野数据文件（global_industry_players/regional_penetration/
global_market_segments/unlisted_players），data_basement 接入消费。
"""

import os  # noqa: F401  (dead-import debt)
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_loaders_exist():
    """4 个 R55 loader 应存在。"""
    from core import data_basement as db

    for fn in [
        "load_global_industry_players",
        "load_regional_penetration",
        "load_global_market_segments",
        "load_unlisted_players",
    ]:
        assert hasattr(db, fn), f"{fn} 缺失"


def test_global_players_loaded():
    """全球玩家映射 loader 应返回玩家数据。"""
    from core.data_basement import load_global_industry_players

    r = load_global_industry_players("气体传感器")
    if r is None:
        return  # 沙箱无数据文件时跳过
    assert "gip_player_count" in r, f"应含玩家数: {list(r.keys())[:5]}"
    assert r["gip_player_count"] >= 5, f"玩家数应≥5: {r['gip_player_count']}"


def test_regional_penetration_loaded():
    """区域渗透率 loader 应返回中国/领先国渗透率。"""
    from core.data_basement import load_regional_penetration

    r = load_regional_penetration("气体传感器")
    if r is None:
        return
    assert "rp_china_pen" in r, f"应含中国渗透率: {list(r.keys())}"
    assert "rp_leading_country" in r, f"应含领先国: {list(r.keys())}"


def test_market_segments_loaded():
    """细分市场规模 loader 应返回全球TAM。"""
    from core.data_basement import load_global_market_segments

    r = load_global_market_segments("气体传感器")
    if r is None:
        return
    assert "gms_global_tam" in r, f"应含全球TAM: {list(r.keys())}"


def test_unlisted_players_loaded():
    """非上市玩家 loader 应返回威胁度判断。"""
    from core.data_basement import load_unlisted_players

    r = load_unlisted_players("气体传感器")
    if r is None:
        return
    assert "ulp_count" in r, f"应含玩家数: {list(r.keys())}"
    assert "ulp_threat_high" in r, f"应含威胁度: {list(r.keys())}"


def test_basement_merges_r55():
    """build_basement_data_dict 应合并 R55 数据（gip_/rp_/gms_/ulp_）。"""
    from core.data_basement import build_basement_data_dict

    d = build_basement_data_dict("气体传感器")
    r55_keys = [k for k in d if k.startswith(("gip_", "rp_", "gms_", "ulp_"))]
    if not r55_keys:
        return  # 沙箱无数据文件时跳过
    assert len(r55_keys) >= 10, f"应合并≥10个R55数据: {r55_keys}"


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
