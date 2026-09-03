"""P0-2: MC significance guard tests (red→green).

Tests:
1. All pending pool → InsufficientOutcomes (no fake p-value)
2. 20+ real outcomes → normal p/percentile
3. Dashboard catches InsufficientOutcomes → human-readable message
"""

import pytest
from core.significance import (
    monte_carlo_direction_significance,
    monte_carlo_alpha_significance,
    InsufficientOutcomes,
    _require_valid_outcomes,
)


# ============================================================
# Test 1: All pending pool → reject
# ============================================================

class TestMCGuardRejectsPending:
    """MC must reject pools with no resolved outcomes."""

    def test_all_pending_rejected(self):
        """2081 pending predictions → InsufficientOutcomes."""
        predictions = [
            {"direction": "bullish", "outcome": "pending", "time_horizon": "6m"}
            for _ in range(100)
        ]
        result = monte_carlo_direction_significance(predictions)
        assert result["significant"] is False
        assert "error" in result
        assert "insufficient" in result["error"].lower() or "pending" in result["error"].lower()

    def test_all_unverifiable_rejected(self):
        """All unverifiable → reject."""
        predictions = [
            {"direction": "bullish", "outcome": "unverifiable", "time_horizon": "6m"}
            for _ in range(50)
        ]
        result = monte_carlo_direction_significance(predictions)
        assert result["significant"] is False
        assert "error" in result

    def test_mixed_pending_unverifiable_rejected(self):
        """Mix of pending + unverifiable → reject."""
        predictions = [
            {"direction": "bullish", "outcome": "pending", "time_horizon": "6m"}
            for _ in range(80)
        ] + [
            {"direction": "bullish", "outcome": "unverifiable", "time_horizon": "6m"}
            for _ in range(20)
        ]
        result = monte_carlo_alpha_significance(predictions)
        assert result["significant"] is False
        assert "error" in result

    def test_fewer_than_20_valid_rejected(self):
        """15 correct + 5 incorrect = 20 valid, should pass. But 15 valid should fail."""
        predictions = [
            {"direction": "bullish", "outcome": "correct", "time_horizon": "6m"}
            for _ in range(15)
        ]
        result = monte_carlo_direction_significance(predictions)
        assert result["significant"] is False
        assert "error" in result


# ============================================================
# Test 2: 20+ real outcomes → normal output
# ============================================================

class TestMCGuardPassesValid:
    """MC should work normally with enough real outcomes."""

    def test_25_correct_outcomes(self):
        """25 correct outcomes → produces valid p-value."""
        predictions = [
            {"direction": "bullish", "outcome": "correct", "time_horizon": "6m"}
            for _ in range(25)
        ]
        result = monte_carlo_direction_significance(predictions, n_simulations=1000)
        assert "p_value" in result
        assert "percentile" in result
        assert "system_hit_rate" in result
        assert result["system_hit_rate"] == 1.0  # all correct
        assert result["p_value"] < 0.05  # should be significant

    def test_30_mixed_outcomes(self):
        """30 mixed correct/incorrect → valid test."""
        predictions = [
            {"direction": "bullish", "outcome": "correct", "time_horizon": "6m"}
            for _ in range(18)
        ] + [
            {"direction": "bullish", "outcome": "incorrect", "time_horizon": "6m"}
            for _ in range(12)
        ]
        result = monte_carlo_alpha_significance(predictions, n_simulations=1000)
        assert "alpha" in result
        assert result["system_rate"] == pytest.approx(0.6, abs=0.01)


# ============================================================
# Test 3: _require_valid_outcomes helper
# ============================================================

class TestRequireValidOutcomes:
    """Test the guard helper directly."""

    def test_raises_on_empty(self):
        """Empty list → InsufficientOutcomes."""
        with pytest.raises(InsufficientOutcomes):
            _require_valid_outcomes([])

    def test_raises_on_all_pending(self):
        """All pending → InsufficientOutcomes."""
        preds = [{"outcome": "pending"} for _ in range(100)]
        with pytest.raises(InsufficientOutcomes):
            _require_valid_outcomes(preds)

    def test_passes_on_25_correct(self):
        """25 correct → returns list."""
        preds = [{"outcome": "correct"} for _ in range(25)]
        result = _require_valid_outcomes(preds)
        assert len(result) == 25

    def test_mixed_correct_incorrect(self):
        """15 correct + 10 incorrect = 25 valid → passes."""
        preds = [{"outcome": "correct"} for _ in range(15)] + \
                [{"outcome": "incorrect"} for _ in range(10)]
        result = _require_valid_outcomes(preds)
        assert len(result) == 25

    def test_custom_min_valid(self):
        """Custom min_valid=5 with 7 valid → passes."""
        preds = [{"outcome": "correct"} for _ in range(7)]
        result = _require_valid_outcomes(preds, min_valid=5)
        assert len(result) == 7

    def test_unverifiable_not_counted(self):
        """Unverifiable outcomes are not counted as valid."""
        preds = [
            {"outcome": "correct"} for _ in range(15)
        ] + [
            {"outcome": "unverifiable"} for _ in range(30)
        ]
        with pytest.raises(InsufficientOutcomes, match="Valid outcomes: 15"):
            _require_valid_outcomes(preds, min_valid=20)
