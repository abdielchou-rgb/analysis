# -*- coding: utf-8 -*-
"""P0/P1/P2 回归测试：行业标签回退链 + cited 去重 + retrieved 漏斗。"""

from __future__ import annotations

# ── P0: _industry_tags_for 回退链 ───────────────────────────────────


class TestIndustryTagsFallback:
    """行业标签从三个上游字段回退读取，最后兜底为空。"""

    def _make_ctx(
        self,
        biz_tags=None,
        chart_tags=None,
        universe_industry=None,
    ):
        dc = {}
        if biz_tags is not None:
            dc["biz_model"] = {"industry_tags": biz_tags}
        if chart_tags is not None:
            dc.setdefault("chart_data", {})["industry_tags"] = chart_tags
        if universe_industry is not None:
            dc.setdefault("universe_summary", {})["industry"] = universe_industry
        return {"data_context": dc}

    def test_biz_model优先(self):
        from pipeline.prompt_injectors_p3b import _industry_tags_for

        ctx = self._make_ctx(biz_tags=["白酒", "消费"], chart_tags=["食品饮料"])
        tags, has_real = _industry_tags_for(ctx)
        assert tags == ["白酒", "消费"]
        assert has_real is True

    def test_chart_data兜底(self):
        from pipeline.prompt_injectors_p3b import _industry_tags_for

        ctx = self._make_ctx(chart_tags=["锂电", "新能源"])
        tags, has_real = _industry_tags_for(ctx)
        assert tags == ["锂电", "新能源"]
        assert has_real is True

    def test_universe_summary兜底(self):
        from pipeline.prompt_injectors_p3b import _industry_tags_for

        ctx = self._make_ctx(universe_industry="银行")
        tags, has_real = _industry_tags_for(ctx)
        assert tags == ["银行"]
        assert has_real is True

    def test全空返回空列表(self):
        from pipeline.prompt_injectors_p3b import _industry_tags_for

        tags, has_real = _industry_tags_for({})
        assert tags == []
        assert has_real is False

    def testbiz_model优先于_chart(self):
        """biz_model 有标签时不应降级到 chart_data。"""
        from pipeline.prompt_injectors_p3b import _industry_tags_for

        ctx = self._make_ctx(biz_tags=["白酒"], chart_tags=["食品饮料"])
        tags, _ = _industry_tags_for(ctx)
        assert tags == ["白酒"]

    def test标签最多取5个(self):
        from pipeline.prompt_injectors_p3b import _industry_tags_for

        ctx = self._make_ctx(biz_tags=list("ABCDEFGHIJ"))
        tags, _ = _industry_tags_for(ctx)
        assert len(tags) == 5


# ── P2: cited 去重 ─────────────────────────────────────────────────


class TestCitedDedup:
    """同一 [KB1] 在 5 个段落出现只算 1 次引用。"""

    def test同一KB_ID多次出现只计一次(self):
        from pipeline.checks.kb_citation_mixin import check_kb_citation_coverage

        # 5 个 [KB1] 出现，但只有 1 个唯一 ID
        text = "目标价1571元 [KB1] 合理。[KB1] 支撑。[KB1] 验证。[KB1] 确认。[KB1] 结论。"
        result = check_kb_citation_coverage(text, injected_kb_count=3, injected_mkb_count=0, threshold=0.5)
        # cited = 1 (唯一 KB-ID) + 0 (方法论词) = 1, injected = 3
        # ratio = 1/3 = 33% < 50% → 但 kb_marks >= max(1, 3*0.5)=1 → passed
        assert result.passed is True

    def test多个不同KB_ID各计一次(self):
        from pipeline.checks.kb_citation_mixin import check_kb_citation_coverage

        text = "[KB1] 分析。[KB2] 验证。[KB3] 结论。"
        result = check_kb_citation_coverage(text, injected_kb_count=3, injected_mkb_count=0, threshold=0.5)
        # cited = 3 (唯一 KB-ID) + 0 = 3, ratio = 3/3 = 100%
        assert result.passed is True
        assert result.score >= 0.9

    def test_MKB_ID也去重(self):
        from pipeline.checks.kb_citation_mixin import check_kb_citation_coverage

        text = "[MKB1] 方法。[MKB1] 再引。[MKB2] 补充。"
        result = check_kb_citation_coverage(text, injected_kb_count=0, injected_mkb_count=3, threshold=0.5)
        # cited = 0 + 2 (唯一 MKB-ID) + 0 = 2, ratio = 2/3 = 67%
        assert result.passed is True

    def test无注入时弱检查(self):
        from pipeline.checks.kb_citation_mixin import check_kb_citation_coverage

        text = "分析 [KB1] 合理。"
        result = check_kb_citation_coverage(text, injected_kb_count=0, injected_mkb_count=0)
        # 弱检查：有 KB 标记 → 通过
        assert result.passed is True


# ── P1: retrieved 漏斗 ─────────────────────────────────────────────


class TestRetrievedFunnel:
    """retrieved > injected 时在 Gate detail 中预警截断丢条目。"""

    def test_retrieved预警在details中(self):
        from pipeline.checks.kb_citation_mixin import KbCitationChecksMixin

        mixin = KbCitationChecksMixin()
        # 文本需 >300 字以触发强检查
        mixin.report_text = "分析" * 200 + " [KB1] 合理 [KB2] 验证。"
        mixin.set_kb_injection_counts(kb_count=2, mkb_count=3, retrieved_count=8)
        result = mixin._check_kb_citation_coverage()
        # retrieved=8 > mkb_injected=3 → 截断丢 5 条 → details 含预警
        assert "retrieved=8" in result.details
        assert "截断丢5条" in result.details

    def test_retrieved不大于injected时无预警(self):
        from pipeline.checks.kb_citation_mixin import KbCitationChecksMixin

        mixin = KbCitationChecksMixin()
        # 文本需 >300 字；retrieved ≤ mkb_injected → 不应有截断预警
        mixin.report_text = "分析" * 200 + " [KB1] 合理。"
        mixin.set_kb_injection_counts(kb_count=1, mkb_count=4, retrieved_count=3)
        result = mixin._check_kb_citation_coverage()
        assert "截断丢" not in result.details
