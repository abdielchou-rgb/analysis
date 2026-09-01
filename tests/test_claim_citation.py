# -*- coding: utf-8 -*-
"""P3-2 (2026-09-01): claim-level 溯源骨架测试——数值→数据键→来源映射。

对标 STORM claim-level citation（AUDIT 2026-09-01 点名"引用粒度"差距）：
正文每个含数字的论断应能回溯到 chart_data 数据键与来源。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


from core.claim_citation import (
    annotate_inline,
    append_citation_appendix,
    build_claim_citation_map,
    render_citation_appendix,
    render_numbered_appendix,
)

_REPORT = "中国市场规模2024年达166亿元，同比增长15%。公司营收15.58亿元，毛利率34.5%。行业处于成长期。"
_COLLECTED = {
    "chart_data": {
        "fig_market_size": {"china_2024": 166.0, "yoy": 0.15},
        "fig_company": {"revenue": 15.58, "gross_margin": 0.345},
    }
}


class TestBuildClaimMap:
    def test_claims_found(self):
        claims = build_claim_citation_map(_REPORT, _COLLECTED)
        assert len(claims) == 2  # 两句含命中数字

    def test_claim_refs(self):
        claims = build_claim_citation_map(_REPORT, _COLLECTED)
        assert claims[0]["refs"] == ["fig_market_size"]
        assert claims[1]["refs"] == ["fig_company"]

    def test_no_match_returns_empty(self):
        claims = build_claim_citation_map("没有任何数字匹配的报告内容。", _COLLECTED)
        assert claims == []

    def test_empty_data(self):
        assert build_claim_citation_map(_REPORT, {}) == []


class TestRenderAppendix:
    def test_appendix_renders_table(self):
        claims = build_claim_citation_map(_REPORT, _COLLECTED)
        appendix = render_citation_appendix(claims)
        assert "附录：关键数据溯源" in appendix
        assert "fig_market_size" in appendix
        assert "166" in appendix

    def test_empty_claims_no_appendix(self):
        assert render_citation_appendix([]) == ""


class TestAppend:
    def test_appends_to_report(self):
        out = append_citation_appendix(_REPORT, _COLLECTED)
        assert "附录：关键数据溯源" in out

    def test_idempotent(self):
        out1 = append_citation_appendix(_REPORT, _COLLECTED)
        out2 = append_citation_appendix(out1, _COLLECTED)
        assert out1 == out2
        assert out1.count("关键数据溯源") == 1

    def test_no_match_unchanged(self):
        text = "纯文字内容没有命中。"
        assert append_citation_appendix(text, _COLLECTED) == text


class TestRenderNumberedAppendix:
    def test_renders_numbered_list(self):
        claims = build_claim_citation_map(_REPORT, _COLLECTED)
        appendix = render_numbered_appendix(claims)
        assert "附录：数据溯源注释" in appendix
        assert "[注1]" in appendix
        assert "fig_market_size" in appendix

    def test_empty_claims_no_appendix(self):
        assert render_numbered_appendix([]) == ""


class TestAnnotateInline:
    def test_basic(self):
        text, claims = annotate_inline(_REPORT, _COLLECTED)
        assert "[注1]" in text
        assert len(claims) == 2

    def test_returns_tuple(self):
        result = annotate_inline(_REPORT, _COLLECTED)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_no_match(self):
        text, claims = annotate_inline("纯文字没有数字匹配。", _COLLECTED)
        assert text == "纯文字没有数字匹配。"
        assert claims == []

    def test_idempotent(self):
        text1, _ = annotate_inline(_REPORT, _COLLECTED)
        text2, _ = annotate_inline(text1, _COLLECTED)
        assert text1 == text2

    def test_max_markers(self):
        text, claims = annotate_inline(_REPORT, _COLLECTED, max_markers=1)
        assert "[注1]" in text
        # 第二个 claim 不应在正文中被标记
        assert "[注2]" not in text.split("附录")[0]
