"""claim 级溯源映射单元测试。

P3-audit 2026-08-24：数字→数据键→来源 的确定性匹配链。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.claim_citation import (
    append_citation_appendix,
    build_claim_citation_map,
)

COLLECTED = {
    "chart_data": {
        "fig_market_size_global": {"2024": 32.5, "2025": 34.8},
        "fig_revenue_trend": {"2023": 10.72, "2024": 12.1},
    },
    "items": [
        {"key": "fig_market_size_global", "source": "enrich: 行业权威口径"},
        {"key": "fig_revenue_trend", "source": "akshare 财务摘要"},
    ],
}

REPORT = (
    "# 深度报告\n\n"
    "全球市场规模2025年达到34.8亿美元，行业进入稳态增长期。\n"
    "公司2023年营收为10.72亿元，同比稳健。\n"
    "我们判断竞争格局将维持三强态势。"
)


@pytest.mark.unit
def test_numbers_matched_to_fig_keys():
    claims = build_claim_citation_map(REPORT, COLLECTED)
    assert len(claims) >= 2, "应至少命中市场规模与营收两句"
    all_refs = {r for c in claims for r in c["refs"]}
    assert "fig_market_size_global" in all_refs
    assert "fig_revenue_trend" in all_refs


@pytest.mark.unit
def test_sources_flow_through():
    claims = build_claim_citation_map(REPORT, COLLECTED)
    sources = {s for c in claims for s in c["sources"]}
    assert any("enrich" in s or "akshare" in s for s in sources)


@pytest.mark.unit
def test_non_numeric_sentences_ignored():
    claims = build_claim_citation_map(REPORT, COLLECTED)
    assert not any("三强态势" in c["claim"] and c["refs"] for c in claims)


@pytest.mark.unit
def test_appendix_render_and_append():
    out = append_citation_appendix(REPORT, COLLECTED)
    assert "## 附录：关键数据溯源" in out
    assert "| 正文论断 | 数据键 | 来源 |" in out
    assert out.startswith(REPORT.rstrip()[:50])  # 原文在前，附录在后


@pytest.mark.unit
def test_no_match_returns_original():
    empty_cd = {"chart_data": {}}
    assert append_citation_appendix(REPORT, empty_cd) == REPORT


@pytest.mark.unit
def test_tolerance_boundary():
    """±0.5% 内命中；超出则不命中。"""
    cd = {"chart_data": {"k": {"v": 100.0}}, "items": []}
    inside = append_citation_appendix("数值为100.3个单位。", cd)
    outside = append_citation_appendix("数值为102.0个单位。", cd)
    assert "附录：关键数据溯源" in inside
    assert "附录：关键数据溯源" not in outside
