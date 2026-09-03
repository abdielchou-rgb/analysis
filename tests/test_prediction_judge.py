"""M1-W1: prediction_judge.py tests."""

import pytest
import sys
sys.path.insert(0, ".")

from core.prediction_judge import judge_outcome, JUDGE_VER, ALPHA_HIT_THRESHOLD, ALPHA_MISS_THRESHOLD


class TestJudgeAlphaBased:
    """Test alpha-based judge with benchmark."""

    def test_bullish_high_alpha_hit(self):
        """Bullish + alpha > 2% → hit."""
        result = judge_outcome(actual_return=0.10, direction="bullish", bench_return=0.05)
        assert result["outcome"] == "hit"
        assert result["alpha"] == pytest.approx(0.05, abs=0.01)
        assert result["bench"] == "provided"

    def test_bullish_low_alpha_miss(self):
        """Bullish + alpha < -2% → miss."""
        result = judge_outcome(actual_return=-0.05, direction="bullish", bench_return=0.05)
        assert result["outcome"] == "miss"
        assert result["alpha"] == pytest.approx(-0.10, abs=0.01)

    def test_bullish_neutral_alpha_partial(self):
        """Bullish + alpha in [-2%, +2%] → partial."""
        result = judge_outcome(actual_return=0.05, direction="bullish", bench_return=0.04)
        assert result["outcome"] == "partial"
        assert result["alpha"] == pytest.approx(0.01, abs=0.01)

    def test_bearish_negative_alpha_hit(self):
        """Bearish + alpha < -2% → hit (market dropped more)."""
        result = judge_outcome(actual_return=-0.10, direction="bearish", bench_return=0.05)
        assert result["outcome"] == "hit"
        assert result["alpha"] == pytest.approx(-0.15, abs=0.01)

    def test_bearish_positive_alpha_miss(self):
        """Bearish + alpha > +2% → miss (market rose)."""
        result = judge_outcome(actual_return=0.05, direction="bearish", bench_return=-0.05)
        assert result["outcome"] == "miss"
        assert result["alpha"] == pytest.approx(0.10, abs=0.01)


class TestJudgeDirectionDegraded:
    """Test direction-based judge (degraded, no benchmark)."""

    def test_bullish_positive_return_hit(self):
        """Bullish + positive return → hit (degraded)."""
        result = judge_outcome(actual_return=0.10, direction="bullish", bench_return=None)
        assert result["outcome"] == "hit"
        assert result["bench"] == "none"
        assert "degraded" in result["detail"]

    def test_bullish_negative_return_miss(self):
        """Bullish + negative return → miss (degraded)."""
        result = judge_outcome(actual_return=-0.05, direction="bullish", bench_return=None)
        assert result["outcome"] == "miss"
        assert result["bench"] == "none"

    def test_bearish_negative_return_hit(self):
        """Bearish + negative return → hit (degraded)."""
        result = judge_outcome(actual_return=-0.10, direction="bearish", bench_return=None)
        assert result["outcome"] == "hit"
        assert result["bench"] == "none"

    def test_bearish_positive_return_miss(self):
        """Bearish + positive return → miss (degraded)."""
        result = judge_outcome(actual_return=0.05, direction="bearish", bench_return=None)
        assert result["outcome"] == "miss"
        assert result["bench"] == "none"

    def test_neutral_always_partial(self):
        """Neutral → always partial."""
        result = judge_outcome(actual_return=0.10, direction="neutral", bench_return=None)
        assert result["outcome"] == "partial"


class TestJudgeTargetPrice:
    """Test target price judge (strictest)."""

    def test_bullish_target_hit(self):
        """Bullish + price >= target → hit."""
        result = judge_outcome(
            actual_return=0.20, direction="bullish",
            bench_return=0.05, target_price=260.0, price_at_expiry=270.0
        )
        assert result["outcome"] == "hit"
        assert "target_hit" in result["detail"]

    def test_bullish_target_not_hit(self):
        """Bullish + price < target → falls back to alpha judge."""
        result = judge_outcome(
            actual_return=0.10, direction="bullish",
            bench_return=0.05, target_price=260.0, price_at_expiry=250.0
        )
        # Falls back to alpha judge
        assert result["outcome"] in ("hit", "miss", "partial")

    def test_bearish_target_hit(self):
        """Bearish + price <= target → hit."""
        result = judge_outcome(
            actual_return=-0.20, direction="bearish",
            bench_return=0.05, target_price=80.0, price_at_expiry=75.0
        )
        assert result["outcome"] == "hit"
        assert "target_hit" in result["detail"]


class TestJudgeVersion:
    """Test judge version tracking."""

    def test_judge_ver_is_2(self):
        assert JUDGE_VER == 2

    def test_result_includes_judge_ver(self):
        result = judge_outcome(actual_return=0.10, direction="bullish", bench_return=0.05)
        assert result["judge_ver"] == JUDGE_VER

    def test_degraded_judge_marked(self):
        result = judge_outcome(actual_return=0.10, direction="bullish", bench_return=None)
        assert result["bench"] == "none"
        assert "degraded" in result["detail"]
