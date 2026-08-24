"""_normalize_indicator 词边界回归测试。

P3-audit 2026-08-24：裸子串匹配把 revision_slope 尾部的 "pe" 归入 PE
冲突簇（真实 E2E 触发"值相差375040%"误报）。词边界后必须隔离。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.data_caliber import _normalize_indicator


@pytest.mark.unit
@pytest.mark.parametrize(
    "key",
    [
        "consensus_revision_slope",
        "revision_slope",
        "fig_revision_breadth",
    ],
)
def test_slope_keys_not_pe(key):
    assert _normalize_indicator(key) != "pe", f"{key} 不应归入 PE 簇"


@pytest.mark.unit
@pytest.mark.parametrize(
    "key,expected",
    [
        ("fig_pe_ttm", "pe"),
        ("pe_forward", "pe"),
        ("consensus_pe_forward", "pe"),
        ("fig_revenue_trend_2024", "revenue"),
        ("fig_margin_gross_2025", "margin"),
    ],
)
def test_legit_indicators_still_cluster(key, expected):
    assert expected in _normalize_indicator(key), f"{key} 应仍归入 {expected}"


@pytest.mark.unit
def test_chinese_indicators_substring_kept():
    assert "毛利率" in _normalize_indicator("fig_gross_margin_毛利率")
