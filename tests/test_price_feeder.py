"""P0-1: Price feeder tests (red→green).

Tests:
1. get_price returns float >0 on success
2. All backends fail → returns None (never fabricates)
3. resolve_outcome with None → unverifiable + data_unavailable
4. No 0.0 placeholder in resolve path
"""

import pytest
from unittest.mock import patch, MagicMock


# ============================================================
# Test 1: get_price returns float on success
# ============================================================

class TestGetPriceSuccess:
    """Test successful price fetching."""

    def test_get_price_akshare_mock(self):
        """Mock akshare → returns float >0."""
        from core.price_feeder import get_price

        mock_df = MagicMock()
        mock_df.iloc = [MagicMock()]
        mock_df.iloc[0] = {"收盘": 260.5}
        mock_df.empty = False

        with patch("core.price_feeder._fetch_akshare", return_value=260.5):
            price = get_price("300750", "2026-06-01", backend="akshare")
            assert price == 260.5
            assert isinstance(price, float)

    def test_get_price_yfinance_mock(self):
        """Mock yfinance → returns float >0."""
        from core.price_feeder import get_price

        with patch("core.price_feeder._fetch_yfinance", return_value=150.0):
            price = get_price("AAPL", "2026-06-01", backend="yfinance")
            assert price == 150.0


# ============================================================
# Test 2: All backends fail → None (never fabricate)
# ============================================================

class TestGetPriceFailure:
    """Test that failures return None, never 0.0 or fabricated."""

    def test_all_backends_fail(self):
        """All backends fail → None."""
        from core.price_feeder import get_price

        with patch("core.price_feeder._fetch_akshare", return_value=None), \
             patch("core.price_feeder._fetch_yfinance", return_value=None):
            price = get_price("300750", "2026-06-01")
            assert price is None

    def test_mock_backend_returns_none(self):
        """Mock backend → None."""
        from core.price_feeder import get_price

        price = get_price("300750", "2026-06-01", backend="mock")
        assert price is None

    def test_no_zero_placeholder(self):
        """Ensure 0.0 is not returned as a placeholder."""
        from core.price_feeder import get_price

        with patch("core.price_feeder._fetch_akshare", return_value=None), \
             patch("core.price_feeder._fetch_yfinance", return_value=None):
            price = get_price("300750", "2026-06-01")
            assert price != 0.0
            assert price is None


# ============================================================
# Test 3: resolve_outcome with None → unverifiable
# ============================================================

class TestResolveOutcomeUnverifiable:
    """Test that missing prices produce unverifiable, not hit/miss."""

    def test_resolve_outcome_no_price(self):
        """No price available → outcome=unverifiable."""
        from scripts.update_outcomes import resolve_outcome

        prediction = {
            "asset": "300750",
            "direction": "bullish",
            "made_date": "2026-01-01",
            "expiry_date": "2026-06-01",
            "outcome": "pending",
        }

        with patch("core.price_feeder.get_price_or_unverifiable", return_value={
            "price": None,
            "status": "unverifiable",
            "detail": "data_unavailable:300750@2026-01-01",
        }):
            result = resolve_outcome(prediction)
            assert result["outcome"] == "unverifiable"
            assert "data_unavailable" in result["outcome_reason"]

    def test_resolve_outcome_partial_price(self):
        """One price missing → unverifiable."""
        from scripts.update_outcomes import resolve_outcome

        prediction = {
            "asset": "300750",
            "direction": "bullish",
            "made_date": "2026-01-01",
            "expiry_date": "2026-06-01",
            "outcome": "pending",
        }

        call_count = [0]
        def mock_get_price(asset, date):
            call_count[0] += 1
            if call_count[0] == 1:
                return 260.0  # price_at_make
            return None  # price_at_expiry missing

        result = resolve_outcome(prediction, get_price_func=mock_get_price)
        assert result["outcome"] == "unverifiable"


# ============================================================
# Test 4: No 0.0 placeholder in resolve path
# ============================================================

class TestNoZeroPlaceholder:
    """Ensure no 0.0 values leak into outcome resolution."""

    def test_no_zero_in_resolved_outcome(self):
        """Resolved outcomes never contain 0.0 price."""
        from scripts.update_outcomes import resolve_outcome

        prediction = {
            "asset": "300750",
            "direction": "bullish",
            "made_date": "2026-01-01",
            "expiry_date": "2026-06-01",
            "outcome": "pending",
        }

        # Mock: both prices available
        def mock_get_price(asset, date):
            return 260.0 if "01" in date else 280.0

        result = resolve_outcome(prediction, get_price_func=mock_get_price)
        assert result.get("price_at_make") != 0.0
        assert result.get("price_at_expiry") != 0.0
        assert result["outcome"] in ("hit", "miss")

    def test_unverifiable_never_hit_or_miss(self):
        """Unverifiable outcomes are never classified as hit/miss."""
        from scripts.update_outcomes import resolve_outcome

        prediction = {
            "asset": "300750",
            "direction": "bullish",
            "made_date": "2026-01-01",
            "expiry_date": "2026-06-01",
            "outcome": "pending",
        }

        with patch("core.price_feeder.get_price_or_unverifiable", return_value={
            "price": None,
            "status": "unverifiable",
            "detail": "data_unavailable",
        }):
            result = resolve_outcome(prediction)
            assert result["outcome"] not in ("hit", "miss", "unverifiable") or result["outcome"] == "unverifiable"
            assert result["outcome"] == "unverifiable"


# ============================================================
# Test 5: price_feeder helpers
# ============================================================

class TestPriceFeederHelpers:
    """Test helper functions in price_feeder."""

    def test_is_a_share(self):
        """A-share detection works."""
        from core.price_feeder import _is_a_share

        assert _is_a_share("300750") is True
        assert _is_a_share("宁德时代") is True
        assert _is_a_share("AAPL") is False
        assert _is_a_share("300750.HK") is False

    def test_is_hk_share(self):
        """HK share detection works."""
        from core.price_feeder import _is_hk_share

        assert _is_hk_share("300750.HK") is True
        assert _is_hk_share("00700") is True
        assert _is_hk_share("300750") is False

    def test_normalize_date(self):
        """Date normalization works."""
        from core.price_feeder import _normalize_date

        assert _normalize_date("2026-06-01") == "2026-06-01"
        assert _normalize_date("20260601") == "2026-06-01"
        assert _normalize_date("2026/06/01") == "2026-06-01"

    def test_get_price_or_unverifiable_success(self):
        """get_price_or_unverifiable returns verified on success."""
        from core.price_feeder import get_price_or_unverifiable

        with patch("core.price_feeder._fetch_akshare", return_value=260.0):
            result = get_price_or_unverifiable("300750", "2026-06-01")
            assert result["status"] == "verified"
            assert result["price"] == 260.0

    def test_get_price_or_unverifiable_failure(self):
        """get_price_or_unverifiable returns unverifiable on failure."""
        from core.price_feeder import get_price_or_unverifiable

        with patch("core.price_feeder._fetch_akshare", return_value=None), \
             patch("core.price_feeder._fetch_yfinance", return_value=None):
            result = get_price_or_unverifiable("300750", "2026-06-01")
            assert result["status"] == "unverifiable"
            assert result["price"] is None
