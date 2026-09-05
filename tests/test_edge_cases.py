"""Edge case tests for robustness verification.

Tests boundary conditions, empty inputs, and error paths.
"""

import json
from unittest.mock import MagicMock

import pytest

# ============================================================
# Significance edge cases
# ============================================================


class TestSignificanceEdgeCases:
    """Test MC significance with edge cases."""

    def test_empty_predictions(self):
        """Empty predictions list returns error."""
        from core.significance import monte_carlo_direction_significance

        result = monte_carlo_direction_significance([])
        assert "error" in result
        assert result["significant"] is False

    def test_single_prediction(self):
        """Single prediction returns error (need >=10)."""
        from core.significance import monte_carlo_direction_significance

        result = monte_carlo_direction_significance([{"outcome": "hit"}])
        assert "error" in result

    def test_exactly_10_predictions(self):
        """Exactly 10 predictions → P0-2 guard (min_valid=20) 应拒绝并返回 error。

        注（2026-09-04）：此前断言 10 个可运行，但 significance.py 的 P0-2
        guard 后来把最小有效样本提到 20（统计功效要求），10 个返回
        error 是预期行为。20 个 hit 的场景由 test_all_correct 覆盖。
        """
        from core.significance import monte_carlo_direction_significance

        predictions = [{"outcome": "hit"} for _ in range(10)]
        result = monte_carlo_direction_significance(predictions, n_simulations=100)
        assert "error" in result, "10 < min_valid=20，应返回 insufficient 错误"

    def test_exactly_20_predictions(self):
        """Exactly 20 predictions is minimum viable (P0-2 min_valid=20)."""
        from core.significance import monte_carlo_direction_significance

        predictions = [{"outcome": "hit"} for _ in range(20)]
        result = monte_carlo_direction_significance(predictions, n_simulations=100)
        assert "error" not in result
        assert result["system_hit_rate"] == 1.0

    def test_all_correct(self):
        """All correct predictions → p_value should be very small."""
        from core.significance import monte_carlo_direction_significance

        predictions = [{"outcome": "hit"} for _ in range(20)]
        result = monte_carlo_direction_significance(predictions, n_simulations=100)
        assert result["system_hit_rate"] == 1.0
        assert result["p_value"] < 0.05

    def test_all_incorrect(self):
        """All incorrect predictions → extreme deviation from 50% benchmark."""
        from core.significance import monte_carlo_direction_significance

        predictions = [{"outcome": "miss"} for _ in range(20)]
        result = monte_carlo_direction_significance(predictions, n_simulations=100)
        assert result["system_hit_rate"] == 0.0
        # 0% hit rate is extreme deviation; percentile should be low
        assert result["percentile"] < 5.0

    def test_50_50_split(self):
        """50/50 split → p_value should be ~0.5."""
        from core.significance import monte_carlo_direction_significance

        predictions = [{"outcome": "hit"} for _ in range(10)] + [{"outcome": "miss"} for _ in range(10)]
        result = monte_carlo_direction_significance(predictions, n_simulations=100)
        assert 0.3 < result["p_value"] < 0.7

    def test_reproducible_with_seed(self):
        """Same seed produces same results."""
        from core.significance import monte_carlo_direction_significance

        predictions = [{"outcome": "hit"} for _ in range(15)] + [{"outcome": "miss"} for _ in range(5)]

        r1 = monte_carlo_direction_significance(predictions, random_seed=42)
        r2 = monte_carlo_direction_significance(predictions, random_seed=42)
        assert r1["p_value"] == r2["p_value"]
        assert r1["percentile"] == r2["percentile"]

    def test_batch_by_horizon(self):
        """Batch by horizon works."""
        from core.significance import batch_significance_by_horizon

        predictions = [
            {"outcome": "hit", "time_horizon": "6m"},
            {"outcome": "hit", "time_horizon": "6m"},
            {"outcome": "miss", "time_horizon": "6m"},
            {"outcome": "hit", "time_horizon": "12m"},
            {"outcome": "hit", "time_horizon": "12m"},
            {"outcome": "hit", "time_horizon": "12m"},
            {"outcome": "hit", "time_horizon": "12m"},
            {"outcome": "hit", "time_horizon": "12m"},
            {"outcome": "miss", "time_horizon": "12m"},
            {"outcome": "hit", "time_horizon": "12m"},
            {"outcome": "hit", "time_horizon": "12m"},
        ]

        result = batch_significance_by_horizon(predictions, n_simulations=100)
        assert "6m" in result
        assert "12m" in result
        assert result["6m"]["count"] == 3
        assert result["12m"]["count"] == 8


# ============================================================
# Attribution edge cases
# ============================================================


class TestAttributionEdgeCases:
    """Test attribution with edge cases."""

    def test_empty_predictions(self):
        """Empty predictions returns empty dict."""
        from core.attribution import attribute_by_dimension

        result = attribute_by_dimension([])
        assert result == {}

    def test_no_dimensions_used(self):
        """Predictions without dimensions_used returns empty."""
        from core.attribution import attribute_by_dimension

        predictions = [
            {"outcome": "hit", "confidence_at_make": 0.8},
            {"outcome": "miss", "confidence_at_make": 0.6},
        ]

        result = attribute_by_dimension(predictions)
        assert result == {}

    def test_ic_perfect_correlation(self):
        """Perfect correlation → IC = 1.0."""
        from core.attribution import compute_ic

        predicted = list(range(1, 21))
        actual = list(range(1, 21))

        result = compute_ic(predicted, actual)
        assert result["ic"] == pytest.approx(1.0, abs=0.01)

    def test_ic_inverse_correlation(self):
        """Inverse correlation → IC ≈ -1.0."""
        from core.attribution import compute_ic

        predicted = list(range(1, 21))
        actual = list(range(20, 0, -1))

        result = compute_ic(predicted, actual)
        assert result["ic"] == pytest.approx(-1.0, abs=0.01)

    def test_ic_no_correlation(self):
        """Random data → IC ≈ 0."""
        # Use fixed seed for reproducibility
        import random

        from core.attribution import compute_ic

        rng = random.Random(42)
        predicted = [rng.random() for _ in range(100)]
        actual = [rng.random() for _ in range(100)]

        result = compute_ic(predicted, actual)
        assert abs(result["ic"]) < 0.3  # Should be close to 0


# ============================================================
# Cohort edge cases
# ============================================================


class TestCohortEdgeCases:
    """Test cohort with edge cases."""

    def test_empty_cohort_stats(self):
        """Empty cohort returns zero stats."""
        from core.cohort import LiveForwardCohort

        cohort = LiveForwardCohort.__new__(LiveForwardCohort)
        stats = cohort.cohort_stats([])
        assert stats["total"] == 0
        assert stats["hit_rate"] == 0

    def test_all_pending_cohort_stats(self):
        """All pending → resolved=0, hit_rate=0."""
        from core.cohort import LiveForwardCohort

        cohort = LiveForwardCohort.__new__(LiveForwardCohort)
        stats = cohort.cohort_stats(
            [
                {"outcome": "pending"},
                {"outcome": "pending"},
            ]
        )
        assert stats["total"] == 2
        assert stats["resolved"] == 0
        assert stats["hit_rate"] == 0

    def test_fixed_asset_pool_empty(self):
        """Empty predictions → empty pool."""
        from core.cohort import LiveForwardCohort

        cohort = LiveForwardCohort.__new__(LiveForwardCohort)
        cohort.load_predictions = MagicMock(return_value=[])
        pool = cohort.fixed_asset_pool()
        assert pool == []


# ============================================================
# Dashboard edge cases
# ============================================================


class TestDashboardEdgeCases:
    """Test dashboard with edge cases."""

    def test_dashboard_no_predictions(self, tmp_path):
        """Dashboard handles missing track record."""
        from core.dashboard import generate_dashboard

        track_record = tmp_path / "track_record.json"
        track_record.write_text(json.dumps({"predictions": []}))

        dashboard = generate_dashboard(
            output_dir=str(tmp_path),
            track_record_path=str(track_record),
        )

        assert dashboard["summary"]["total_predictions"] == 0
        assert dashboard["summary"]["hit_rate"] == 0

    def test_dashboard_missing_track_record(self, tmp_path):
        """Dashboard handles missing track record file."""
        from core.dashboard import generate_dashboard

        dashboard = generate_dashboard(
            output_dir=str(tmp_path),
            track_record_path=str(tmp_path / "nonexistent.json"),
        )

        assert dashboard["summary"]["total_predictions"] == 0


# ============================================================
# Timeline edge cases
# ============================================================


class TestTimelineEdgeCases:
    """Test prediction timeline with edge cases."""

    def test_empty_timeline(self, tmp_path):
        """Empty timeline returns empty updates."""
        from core.prediction_timeline import PredictionTimeline

        timeline_path = tmp_path / "timelines.json"
        manager = PredictionTimeline(timeline_path=str(timeline_path))

        timeline = manager.get_timeline("nonexistent")
        assert timeline["updates"] == []

    def test_multiple_updates(self, tmp_path):
        """Multiple updates are recorded in order."""
        from core.prediction_timeline import PredictionTimeline

        timeline_path = tmp_path / "timelines.json"
        manager = PredictionTimeline(timeline_path=str(timeline_path))

        manager.record_update("pred_001", "revision", "target_price", "350", "387.5")
        manager.record_update("pred_001", "confidence_change", "confidence", "0.7", "0.8")
        manager.record_update("pred_001", "revision", "target_price", "387.5", "400")

        timeline = manager.get_timeline("pred_001")
        assert len(timeline["updates"]) == 3
        assert timeline["current_state"]["target_price"] == "400"
        # Confidence is stored as string via str()
        assert str(timeline["current_state"]["confidence"]) == "0.8"


# ============================================================
# HITL edge cases
# ============================================================


class TestHITLEdgeCases:
    """Test HITL durable with edge cases."""

    def test_approve_nonexistent(self, tmp_path):
        """Approving nonexistent job returns False."""
        from core.hitl_durable import HITLApprovalManager

        manager = HITLApprovalManager(
            review_dir=str(tmp_path / "reviews"),
            ledger_dir=str(tmp_path / "ledgers"),
        )

        result = manager.approve("nonexistent")
        assert result is False

    def test_reject_nonexistent(self, tmp_path):
        """Rejecting nonexistent job returns False."""
        from core.hitl_durable import HITLApprovalManager

        manager = HITLApprovalManager(
            review_dir=str(tmp_path / "reviews"),
            ledger_dir=str(tmp_path / "ledgers"),
        )

        result = manager.reject("nonexistent")
        assert result is False

    def test_check_nonexistent(self, tmp_path):
        """Checking nonexistent job returns not_found."""
        from core.hitl_durable import HITLApprovalManager

        manager = HITLApprovalManager(
            review_dir=str(tmp_path / "reviews"),
            ledger_dir=str(tmp_path / "ledgers"),
        )

        result = manager.check_approval("nonexistent")
        assert result["status"] == "not_found"

    def test_stale_approvals(self, tmp_path):
        """Finding stale approvals works."""
        from core.hitl_durable import HITLApprovalManager

        review_dir = tmp_path / "reviews"
        review_dir.mkdir()
        ledger_dir = tmp_path / "ledgers"
        ledger_dir.mkdir()

        manager = HITLApprovalManager(
            review_dir=str(review_dir),
            ledger_dir=str(ledger_dir),
        )

        # Create a pending approval
        manager.request_approval("job_001", "test_asset", "test_type")

        # Find stale
        stale = manager.find_stale_approvals()
        assert len(stale) == 1
        assert stale[0]["job_id"] == "job_001"


# ============================================================
# Retry policy edge cases
# ============================================================


class TestRetryEdgeCases:
    """Test retry policy with edge cases."""

    def test_rate_limit_error(self):
        """Rate limit error classified correctly."""
        from core.retry_policy import ErrorClass, RetryPolicy

        policy = RetryPolicy()
        error_class = policy.classify_error(Exception("429 rate limit"))
        assert error_class == ErrorClass.RETRYABLE_RATE_LIMIT

    def test_context_too_long(self):
        """Context too long error classified correctly."""
        from core.retry_policy import ErrorClass, RetryPolicy

        policy = RetryPolicy()
        error_class = policy.classify_error(Exception("context window exceeded"))
        assert error_class == ErrorClass.RETRYABLE_CONTEXT

    def test_unknown_error(self):
        """Unknown error classified correctly."""
        from core.retry_policy import ErrorClass, RetryPolicy

        policy = RetryPolicy()
        error_class = policy.classify_error(RuntimeError("something weird"))
        assert error_class == ErrorClass.UNKNOWN


# ============================================================
# DataPoint edge cases
# ============================================================


class TestDataPointEdgeCases:
    """Test DataPoint with edge cases."""

    def test_minimal_datapoint(self):
        """DataPoint with minimal fields works."""
        from core.models import DataPoint

        dp = DataPoint(
            name="test",
            value=0,
            unit="",
            source="test",
            access_ts="2026-09-02T00:00:00Z",
            excerpt_sha256="a",
            confidence=0.0,
            scope="company",
        )
        assert dp.value == 0
        assert dp.confidence == 0.0

    def test_large_values(self):
        """DataPoint with large values works."""
        from core.models import DataPoint

        dp = DataPoint(
            name="market_cap",
            value=1e12,
            unit="USD",
            source="test",
            access_ts="2026-09-02T00:00:00Z",
            excerpt_sha256="abc",
            confidence=0.95,
            scope="company",
        )
        assert dp.value == 1e12


# ============================================================
# Idempotent ledger edge cases
# ============================================================


class TestLedgerEdgeCases:
    """Test idempotent ledger with edge cases."""

    def test_is_duplicate_empty(self, tmp_path):
        """is_duplicate on empty ledger returns False."""
        from core.idempotent_ledger import IdempotentLedger

        ledger = IdempotentLedger(ledger_dir=str(tmp_path / "ledgers"))
        result = ledger.is_duplicate("export", "test_asset", {"job_id": "job_001"})
        assert result is False

    def test_get_pending_empty(self, tmp_path):
        """get_pending on empty ledger returns empty list."""
        from core.idempotent_ledger import IdempotentLedger

        ledger = IdempotentLedger(ledger_dir=str(tmp_path / "ledgers"))
        pending = ledger.get_pending()
        assert pending == []


# ============================================================
# Golden validation edge cases
# ============================================================


class TestGoldenEdgeCases:
    """Test golden validation with edge cases."""

    def test_text_similarity_identical(self):
        """Identical texts → similarity = 1.0."""
        from scripts.validate_golden import compute_text_similarity

        text = "Hello world. This is a test."
        result = compute_text_similarity(text, text)
        assert result == 1.0

    def test_text_similarity_empty(self):
        """Empty texts → similarity = 0.0."""
        from scripts.validate_golden import compute_text_similarity

        result = compute_text_similarity("", "")
        assert result == 0.0

    def test_structure_similarity_identical(self):
        """Identical structures → similarity = 1.0."""
        from scripts.validate_golden import compute_structure_similarity

        text = "# Heading\n- Item 1\n- Item 2\n| col1 | col2 |"
        result = compute_structure_similarity(text, text)
        assert result == 1.0
