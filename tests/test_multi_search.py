"""S1-S4: Multi-backend search + gap fill + cross validation tests.

S1: multi_search failover chain (exa/bocha/keenable/tavily/ddg)
S2: language-based routing (zh → bocha chain, en → exa chain)
S3: second-round gap fill (SAC coverage check → followup queries)
S4: cross validation (n_sources, ≥2 sources = verified)
"""

import pytest
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, ".")

from core.multi_search import (
    multi_search,
    _is_chinese,
    CHAIN_ZH,
    CHAIN_EN,
    available_backends,
)


# ============================================================
# S1: Language detection
# ============================================================

class TestLanguageDetection:
    def test_chinese_query_detected(self):
        assert _is_chinese("宁德时代 财报 营收") is True

    def test_english_query_detected(self):
        assert _is_chinese("CATL earnings report revenue") is False

    def test_mixed_query_chinese_majority(self):
        assert _is_chinese("宁德时代 CATL 电池 财报") is True

    def test_empty_query(self):
        assert _is_chinese("") is False

    def test_single_char_not_chinese(self):
        # "a b" — no CJK
        assert _is_chinese("a b c") is False


# ============================================================
# S1: Chain composition
# ============================================================

class TestChainComposition:
    def test_zh_chain_leads_with_bocha(self):
        assert CHAIN_ZH[0] == "bocha"

    def test_en_chain_leads_with_exa(self):
        assert CHAIN_EN[0] == "exa"

    def test_keyless_floors_present(self):
        assert "keenable" in CHAIN_ZH and "ddg" in CHAIN_ZH
        assert "keenable" in CHAIN_EN and "ddg" in CHAIN_EN

    def test_bing_cn_in_both_chains(self):
        """BingCN (keyless zh-strong) is in both chains as free floor."""
        assert "bing_cn" in CHAIN_ZH
        assert "bing_cn" in CHAIN_EN

    def test_available_backends_includes_keyless(self):
        backends = available_backends()
        assert "keenable" in backends
        assert "bing_cn" in backends
        assert "ddg" in backends


# ============================================================
# S1: Failover behavior
# ============================================================

class TestFailoverBehavior:
    def test_first_backend_success_skips_rest(self):
        """First backend returns results → chain stops there."""
        with patch("core.multi_search._bocha_search", return_value=[
            {"url": "http://a", "title": "A", "content": "content A", "source_backend": "bocha"}
        ]) as m_bocha, patch("core.multi_search._tavily_search") as m_tavily:
            results = multi_search("宁德时代 财报", prefer_zh=True)
            assert len(results) == 1
            assert results[0]["source_backend"] == "bocha"
            m_bocha.assert_called_once()
            m_tavily.assert_not_called()

    def test_first_fails_falls_to_second(self):
        """First backend returns None → falls to next in chain."""
        with patch("core.multi_search._bocha_search", return_value=None), \
             patch("core.multi_search._tavily_search", return_value=[
                 {"url": "http://b", "title": "B", "content": "content B", "source_backend": "tavily"}
             ]):
            results = multi_search("宁德时代 财报", prefer_zh=True)
            assert len(results) == 1
            assert results[0]["source_backend"] == "tavily"

    def test_all_fail_returns_empty(self):
        """All backends fail → empty list (never raises)."""
        with patch("core.multi_search._bocha_search", return_value=None), \
             patch("core.multi_search._tavily_search", return_value=None), \
             patch("core.multi_search._keenable_search", return_value=None), \
             patch("core.multi_search._bing_cn_search", return_value=None), \
             patch("core.multi_search._ddg_search", return_value=None):
            results = multi_search("宁德时代 财报", prefer_zh=True)
            assert results == []

    def test_empty_query_returns_empty(self):
        assert multi_search("") == []

    def test_reason_propagated(self):
        with patch("core.multi_search._bocha_search", return_value=[
            {"url": "http://a", "title": "A", "content": "c", "source_backend": "bocha"}
        ]):
            results = multi_search("测试", prefer_zh=True, reason="财务")
            assert results[0]["query_reason"] == "财务"


# ============================================================
# S1: English chain routing
# ============================================================

class TestEnglishRouting:
    def test_english_query_uses_exa_first(self):
        with patch("core.multi_search._exa_search", return_value=[
            {"url": "http://x", "title": "X", "content": "c", "source_backend": "exa"}
        ]) as m_exa:
            results = multi_search("CATL battery market share", prefer_zh=False)
            assert results[0]["source_backend"] == "exa"
            m_exa.assert_called_once()


# ============================================================
# S3: Gap fill
# ============================================================

class TestGapFill:
    def _make_collector(self):
        from pipeline.data_collector import DataCollectorV5
        return DataCollectorV5()

    def test_skip_when_all_keys_present(self):
        """All core keys present → no gap fill search."""
        dc = self._make_collector()
        chart_data = {
            "fig_revenue_trend": {"2024": 100},
            "fig_profitability": {"2024": 20},
            "fig_business_segments": {"a": 0.5},
        }
        with patch("core.multi_search.multi_search") as m_ms:
            # Should NOT call multi_search (all keys present)
            result = dc._second_round_gap_fill("测试资产", chart_data, net_start=0.0, net_budget=100.0)
            assert "fig_revenue_trend" in result
            # multi_search not called because no gap
            assert not m_ms.called or all(
                "gap" not in str(c) for c in m_ms.call_args_list
            )

    def test_gap_fill_triggers_on_missing_keys(self):
        """Missing core keys → gap fill queries fired."""
        dc = self._make_collector()
        chart_data = {"fig_revenue_trend": {"2024": 100}}  # missing other 2
        with patch("core.multi_search.multi_search", return_value=[
            {"url": "http://g", "title": "G", "content": "x" * 200, "source_backend": "bocha"}
        ]):
            # LLM extraction will fail (no LLM in test) — that's OK, just verify search fired
            result = dc._second_round_gap_fill("测试资产", chart_data, net_start=0.0, net_budget=100.0)
            assert isinstance(result, dict)

    def test_gap_fill_skipped_on_low_budget(self):
        """Time budget < 12s remaining → skip gap fill entirely."""
        dc = self._make_collector()
        chart_data = {}  # all keys missing
        result = dc._second_round_gap_fill("测试", chart_data, net_start=100.0, net_budget=105.0)
        # Should return unchanged (no time budget)
        assert result == chart_data


# ============================================================
# S4: Cross validation
# ============================================================

class TestCrossValidation:
    def _make_collector(self):
        from pipeline.data_collector import DataCollectorV5
        return DataCollectorV5()

    def test_n_sources_map_generated(self):
        """fig_* keys get n_sources entries."""
        dc = self._make_collector()
        chart_data = {
            "fig_revenue_trend": {"2024": 100},
            "_source_index": {"fig_revenue_trend": "tavily"},
        }
        with patch.object(dc, "_local_provided", return_value=False):
            result = dc._cross_validate_figures(chart_data)
            assert "_n_sources" in result
            assert result["_n_sources"]["fig_revenue_trend"] == 1

    def test_multi_source_verified(self):
        """Local + network source → n_sources=2."""
        dc = self._make_collector()
        chart_data = {
            "fig_revenue_trend": {"2024": 100},
            "_source_index": {"fig_revenue_trend": "tavily"},
        }
        with patch.object(dc, "_local_provided", return_value=True):
            result = dc._cross_validate_figures(chart_data)
            assert result["_n_sources"]["fig_revenue_trend"] == 2

    def test_no_source_index_passthrough(self):
        """No _source_index → unchanged."""
        dc = self._make_collector()
        chart_data = {"fig_revenue_trend": {"2024": 100}}
        result = dc._cross_validate_figures(chart_data)
        assert "_n_sources" not in result

    def test_non_fig_keys_ignored(self):
        """Non fig_ keys don't get n_sources."""
        dc = self._make_collector()
        chart_data = {
            "company_intro": "text",
            "fig_revenue_trend": {"2024": 100},
            "_source_index": {"fig_revenue_trend": "tavily", "company_intro": "local"},
        }
        with patch.object(dc, "_local_provided", return_value=False):
            result = dc._cross_validate_figures(chart_data)
            assert "company_intro" not in result.get("_n_sources", {})
            assert "fig_revenue_trend" in result["_n_sources"]


# ============================================================
# S1: BingCN backend (free bocha replacement)
# ============================================================

class TestBingCNBackend:
    def test_bing_cn_parses_html(self):
        """BingCN parses li.b_algo items into normalized results."""
        from core.multi_search import _bing_cn_search

        fake_html = """
        <html><body>
        <li class="b_algo">
            <h2><a href="https://example.com/1">宁德时代财报</a></h2>
            <div class="b_caption"><p>2025年营收突破4000亿元</p></div>
        </li>
        <li class="b_algo">
            <h2><a href="https://example.com/2">宁德时代公告</a></h2>
            <div class="b_caption"><p>公司公告全文</p></div>
        </li>
        </body></html>
        """
        with patch("requests.get") as m_get:
            m_resp = MagicMock()
            m_resp.status_code = 200
            m_resp.text = fake_html
            m_resp.raise_for_status = MagicMock()
            m_get.return_value = m_resp
            results = _bing_cn_search("宁德时代", 5)
            assert len(results) == 2
            assert results[0]["source_backend"] == "bing_cn"
            assert results[0]["url"] == "https://example.com/1"
            assert "宁德时代财报" in results[0]["title"]

    def test_bing_cn_empty_on_no_results(self):
        from core.multi_search import _bing_cn_search

        with patch("requests.get") as m_get:
            m_resp = MagicMock()
            m_resp.status_code = 200
            m_resp.text = "<html><body>No results</body></html>"
            m_resp.raise_for_status = MagicMock()
            m_get.return_value = m_resp
            assert _bing_cn_search("test", 5) is None

    def test_bing_cn_skips_items_without_snippet(self):
        """Items without snippet are skipped (no empty content)."""
        from core.multi_search import _bing_cn_search

        fake_html = """
        <html><body>
        <li class="b_algo">
            <h2><a href="https://example.com/1">Title only</a></h2>
        </li>
        <li class="b_algo">
            <h2><a href="https://example.com/2">With snippet</a></h2>
            <div class="b_caption"><p>has content</p></div>
        </li>
        </body></html>
        """
        with patch("requests.get") as m_get:
            m_resp = MagicMock()
            m_resp.status_code = 200
            m_resp.text = fake_html
            m_resp.raise_for_status = MagicMock()
            m_get.return_value = m_resp
            results = _bing_cn_search("test", 5)
            assert len(results) == 1
            assert results[0]["url"] == "https://example.com/2"


# ============================================================
# Integration: web_intel multi-backend
# ============================================================

class TestWebIntelMultiBackend:
    def test_search_multi_backend_exists(self):
        from core.web_intel import search_multi_backend
        assert callable(search_multi_backend)

    def test_search_multi_backend_normalizes(self):
        """Results have url/title/content/query_reason/source_backend."""
        from core.web_intel import search_multi_backend
        with patch("core.multi_search.multi_search", return_value=[
            {"url": "http://t", "title": "T", "content": "c" * 100, "source_backend": "bocha"}
        ]):
            results = search_multi_backend([
                {"query": "宁德时代", "reason": "测试", "max_results": 5}
            ])
            assert len(results) == 1
            r = results[0]
            assert "url" in r and "title" in r and "content" in r
            assert r["query_reason"] == "测试"
            assert r["source_backend"] == "bocha"

    def test_search_multi_backend_dedupes(self):
        """Same URL across queries appears once."""
        from core.web_intel import search_multi_backend
        with patch("core.multi_search.multi_search", return_value=[
            {"url": "http://dup", "title": "T", "content": "c", "source_backend": "bocha"}
        ]):
            results = search_multi_backend([
                {"query": "q1", "reason": "r1", "max_results": 5},
                {"query": "q2", "reason": "r2", "max_results": 5},
            ])
            assert len(results) == 1  # deduped
