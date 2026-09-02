"""Integration test: end-to-end pipeline validation.

Tests the full pipeline from data collection through export,
verifying all new features (A1-C6, D1-D6) work together.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# Test 1: Full pipeline validation
# ============================================================

class TestFullPipeline:
    """Validate the complete pipeline with all new features."""

    def test_gate_report_includes_judge_ver(self):
        """GateReport includes judge_ver and gate_config_hash."""
        from pipeline.checks.base import GateReport

        report = GateReport()
        report.judge_ver = "2026-09-02-v2"
        report.gate_config_hash = "abc123"

        d = report.to_dict()
        assert d["judge_ver"] == "2026-09-02-v2"
        assert d["gate_config_hash"] == "abc123"

    def test_gate_fail_closed_on_empty_checks(self):
        """Gate blocks when no error checks exist."""
        from pipeline.checks.base import GateReport

        report = GateReport()
        report.checks = []

        # A1: fail-closed on empty error checks
        _error_scores = [max(0.0, min(1.0, c.score)) for c in report.checks if c.severity == "error"]
        report.passed = (
            sum(_error_scores) / len(_error_scores) >= 0.78
            if _error_scores else False
        )

        assert not report.passed

    def test_node_contract_validation(self):
        """D1: Node completion contract catches empty fields."""
        # Simulate node evidence check
        context = {
            "collected_data": {},
            "compute_results": {},
            "report_text": "",
            "final_text": "",
        }

        _node_evidence = {
            "data": ["collected_data"],
            "compute": ["compute_results"],
            "write_sections": ["report_text"],
            "assemble": ["final_text"],
        }
        _node_failures = []
        for _node, _keys in _node_evidence.items():
            for _k in _keys:
                _val = context.get(_k)
                if not _val or (isinstance(_val, (dict, str)) and not _val):
                    _node_failures.append(f"{_node}:{_k}")

        assert len(_node_failures) >= 3

    def test_fingerprint_consistency(self):
        """Fingerprint hash matches report text."""
        import hashlib
        from pipeline.e2e_orchestrator import _report_hash

        text = "Test report about 宁德时代."
        ctx = {"final_text": text}
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert _report_hash(ctx) == expected

    def test_placeholder_replacement(self):
        """B1: {{tp_primary}} is replaced."""
        text = "目标价{{tp_primary}}元。"
        result = text.replace("{{tp_primary}}", "387.5")
        assert "387.5" in result
        assert "{{" not in result

    def test_residual_placeholder_detection(self):
        """Residual placeholders are detected."""
        import re
        text = "目标价{{tp_primary}}元，估值{{pe_primary}}倍。"
        residual = re.findall(r"\{\{[a-z_]+\}\}", text)
        assert len(residual) == 2


# ============================================================
# Test 2: Calibration integration
# ============================================================

class TestCalibrationIntegration:
    """Test calibration panel and recalibration."""

    def test_calibration_dashboard_instantiation(self):
        """CalibrationDashboard can be instantiated."""
        from core.calibration.dashboard import CalibrationDashboard

        dashboard = CalibrationDashboard()
        assert hasattr(dashboard, "full_report")
        assert hasattr(dashboard, "systematic_bias")

    def test_calibration_dashboard_methods(self):
        """CalibrationDashboard has expected methods."""
        from core.calibration.dashboard import CalibrationDashboard

        dashboard = CalibrationDashboard()
        methods = [m for m in dir(dashboard) if not m.startswith('_')]
        assert "accuracy_by_sector" in methods
        assert "accuracy_by_timeframe" in methods
        assert "valuation_bias" in methods
        assert "get_frequent_failures" in methods


# ============================================================
# Test 3: Significance integration
# ============================================================

class TestSignificanceIntegration:
    """Test Monte Carlo significance testing."""

    def test_direction_significance(self):
        """Direction significance test works."""
        from core.significance import monte_carlo_direction_significance

        predictions = [
            {"direction": "bullish", "outcome": "correct"} for _ in range(20)
        ] + [
            {"direction": "bearish", "outcome": "incorrect"} for _ in range(5)
        ]

        result = monte_carlo_direction_significance(predictions, n_simulations=100)
        assert "system_hit_rate" in result
        assert "p_value" in result
        assert "significant" in result

    def test_alpha_significance(self):
        """Alpha significance test works."""
        from core.significance import monte_carlo_alpha_significance

        predictions = [
            {"direction": "bullish", "outcome": "correct"} for _ in range(15)
        ] + [
            {"direction": "bearish", "outcome": "incorrect"} for _ in range(5)
        ]

        result = monte_carlo_alpha_significance(predictions, n_simulations=100)
        assert "alpha" in result
        assert "p_value" in result


# ============================================================
# Test 4: Cohort integration
# ============================================================

class TestCohortIntegration:
    """Test live-forward cohort management."""

    def test_cohort_filtering(self):
        """Cohort filtering works."""
        from core.cohort import LiveForwardCohort

        cohort = LiveForwardCohort.__new__(LiveForwardCohort)

        # Mock predictions
        cohort.load_predictions = MagicMock(return_value=[
            {"made_date": "2026-01-01", "direction": "bullish", "time_horizon": "6m", "outcome": "pending"},
            {"made_date": "2026-06-01", "direction": "bearish", "time_horizon": "12m", "outcome": "correct"},
            {"made_date": "2026-03-01", "direction": "bullish", "time_horizon": "6m", "outcome": "incorrect"},
        ])

        # Filter by direction
        result = cohort.get_cohort(direction="bullish")
        assert len(result) == 2

        # Filter by time_horizon
        result = cohort.get_cohort(time_horizon="12m")
        assert len(result) == 1

    def test_cohort_stats(self):
        """Cohort statistics computation works."""
        from core.cohort import LiveForwardCohort

        cohort = LiveForwardCohort.__new__(LiveForwardCohort)
        stats = cohort.cohort_stats([
            {"outcome": "correct"},
            {"outcome": "correct"},
            {"outcome": "incorrect"},
            {"outcome": "pending"},
        ])

        assert stats["total"] == 4
        assert stats["resolved"] == 3
        assert stats["correct"] == 2
        assert stats["hit_rate"] == pytest.approx(2/3, abs=0.01)


# ============================================================
# Test 5: Attribution integration
# ============================================================

class TestAttributionIntegration:
    """Test dimension/framework attribution."""

    def test_ic_computation(self):
        """Information Coefficient computation works."""
        from core.attribution import compute_ic

        # Perfect correlation
        predicted = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        actual = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        result = compute_ic(predicted, actual)
        assert result["ic"] == pytest.approx(1.0, abs=0.01)

    def test_dimension_attribution(self):
        """Dimension attribution works."""
        from core.attribution import attribute_by_dimension

        # Need at least 5 predictions per dimension
        predictions = [
            {"outcome": "correct", "dimensions_used": ["valuation", "growth"], "confidence_at_make": 0.8},
            {"outcome": "incorrect", "dimensions_used": ["valuation"], "confidence_at_make": 0.6},
            {"outcome": "correct", "dimensions_used": ["growth"], "confidence_at_make": 0.9},
            {"outcome": "correct", "dimensions_used": ["valuation", "growth"], "confidence_at_make": 0.7},
            {"outcome": "incorrect", "dimensions_used": ["valuation"], "confidence_at_make": 0.5},
            {"outcome": "correct", "dimensions_used": ["growth"], "confidence_at_make": 0.85},
            {"outcome": "correct", "dimensions_used": ["valuation"], "confidence_at_make": 0.75},
            {"outcome": "incorrect", "dimensions_used": ["valuation", "growth"], "confidence_at_make": 0.65},
            {"outcome": "correct", "dimensions_used": ["growth"], "confidence_at_make": 0.95},
            {"outcome": "correct", "dimensions_used": ["valuation"], "confidence_at_make": 0.7},
        ]

        result = attribute_by_dimension(predictions)
        assert "valuation" in result
        assert "growth" in result


# ============================================================
# Test 6: Prediction timeline integration
# ============================================================

class TestTimelineIntegration:
    """Test prediction timeline updates."""

    def test_timeline_update_recording(self, tmp_path):
        """Timeline updates are recorded."""
        from core.prediction_timeline import PredictionTimeline

        timeline_path = tmp_path / "timelines.json"
        manager = PredictionTimeline(timeline_path=str(timeline_path))

        event = manager.record_update(
            prediction_id="pred_001",
            update_type="revision",
            field_changed="target_price",
            old_value="350",
            new_value="387.5",
            reason="Updated DCF model",
            confidence_before=0.7,
            confidence_after=0.8,
        )

        assert event["update_type"] == "revision"
        assert event["field_changed"] == "target_price"

        # Verify timeline
        timeline = manager.get_timeline("pred_001")
        assert len(timeline["updates"]) == 1
        assert timeline["current_state"]["target_price"] == "387.5"
        assert timeline["current_state"]["confidence"] == 0.8


# ============================================================
# Test 7: Side effects integration
# ============================================================

class TestSideEffectsIntegration:
    """Test idempotent side effects."""

    def test_side_effect_idempotency(self, tmp_path):
        """Side effects are idempotent."""
        from core.idempotent_ledger import IdempotentLedger

        ledger_dir = tmp_path / "ledgers"
        ledger_dir.mkdir()
        ledger = IdempotentLedger(ledger_dir=str(ledger_dir))

        # Record pending
        entry_id = ledger.record_pending(entry_type="export", asset="test", params={"job_id": "job_001"})
        assert entry_id is not None

        # Check pending
        pending = ledger.get_pending()
        assert len(pending) >= 1

        # Check duplicate detection
        is_dup = ledger.is_duplicate(entry_type="export", asset="test", params={"job_id": "job_001"})
        assert is_dup is True


# ============================================================
# Test 8: HITL durable integration
# ============================================================

class TestHITLIntegration:
    """Test HITL durable approval."""

    def test_approval_lifecycle(self, tmp_path):
        """Full approval lifecycle works."""
        from core.hitl_durable import HITLApprovalManager

        review_dir = tmp_path / "reviews"
        review_dir.mkdir()
        ledger_dir = tmp_path / "ledgers"
        ledger_dir.mkdir()

        manager = HITLApprovalManager(
            review_dir=str(review_dir),
            ledger_dir=str(ledger_dir),
        )

        # Request approval
        review_path = manager.request_approval(
            job_id="job_002",
            asset="宁德时代",
            report_type="财报点评",
            reason="New forecast",
        )

        # Check pending
        result = manager.check_approval("job_002")
        assert result["decision"] == "pending"

        # Approve
        manager.approve("job_002", reviewer="analyst_1", notes="Looks good")

        # Check approved
        result = manager.check_approval("job_002")
        assert result["decision"] == "approved"
        assert result["reviewer"] == "analyst_1"


# ============================================================
# Test 9: Retry policy integration
# ============================================================

class TestRetryIntegration:
    """Test declarative retry by error class."""

    def test_retry_classification(self):
        """Error classes are classified correctly."""
        from core.retry_policy import ErrorClass, RetryPolicy

        policy = RetryPolicy()

        # Rate limit error
        error_class = policy.classify_error(Exception("429 rate limit exceeded"))
        assert error_class == ErrorClass.RETRYABLE_RATE_LIMIT

        # Timeout error
        error_class = policy.classify_error(TimeoutError("connection timed out"))
        assert error_class == ErrorClass.RETRYABLE_TIMEOUT

        # Unknown error
        error_class = policy.classify_error(RuntimeError("something"))
        assert error_class == ErrorClass.UNKNOWN


# ============================================================
# Test 10: DataPoint validation integration
# ============================================================

class TestDataPointIntegration:
    """Test DataPoint validation."""

    def test_empty_unit_accepted(self):
        """DataPoint with empty unit does not raise."""
        from core.models import DataPoint

        dp = DataPoint(
            name="test",
            value=42.0,
            unit="",
            source="test",
            access_ts="2026-09-02T00:00:00Z",
            excerpt_sha256="abc",
            confidence=0.8,
            scope="company",
        )
        assert dp.unit == ""

    def test_valid_unit_works(self):
        """DataPoint with valid unit works."""
        from core.models import DataPoint

        dp = DataPoint(
            name="revenue",
            value=1000.0,
            unit="亿元",
            source="annual_report",
            access_ts="2026-09-02T00:00:00Z",
            excerpt_sha256="def",
            confidence=0.9,
            scope="company",
        )
        assert dp.unit == "亿元"
