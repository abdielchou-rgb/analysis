"""M0-U1: Outcome vocabulary unification tests.

Verifies that:
1. All core modules use unified vocab {hit, miss, partial, pending, unverifiable, pending_review}
2. No core/script file uses bare "correct" or "incorrect" as outcome values
3. All readers/writers agree on the same vocabulary
"""

import pytest
import sys
sys.path.insert(0, ".")

from core.tools.track_record import OUTCOME_VOCAB, RESOLVED_OUTCOMES, DIRECTION_VOCAB


class TestOutcomeVocabConstant:
    """Test OUTCOME_VOCAB constant is correct."""

    def test_outcome_vocab_contents(self):
        assert OUTCOME_VOCAB == frozenset({
            "pending", "hit", "miss", "partial", "unverifiable", "pending_review"
        })

    def test_resolved_outcomes(self):
        assert RESOLVED_OUTCOMES == frozenset({"hit", "miss", "partial"})

    def test_direction_vocab(self):
        assert DIRECTION_VOCAB == frozenset({"bullish", "bearish", "neutral"})


class TestCoreModulesVocab:
    """Test that core modules use unified vocabulary."""

    def test_significance_uses_hit_miss(self):
        """significance.py should filter on hit/miss, not correct/incorrect."""
        from core.significance import _require_valid_outcomes
        preds_hit_miss = [
            {"outcome": "hit"}, {"outcome": "miss"}, {"outcome": "hit"},
            {"outcome": "miss"}, {"outcome": "hit"}, {"outcome": "miss"},
            {"outcome": "hit"}, {"outcome": "miss"}, {"outcome": "hit"},
            {"outcome": "miss"}, {"outcome": "hit"}, {"outcome": "miss"},
            {"outcome": "hit"}, {"outcome": "miss"}, {"outcome": "hit"},
            {"outcome": "miss"}, {"outcome": "hit"}, {"outcome": "miss"},
            {"outcome": "hit"}, {"outcome": "miss"},
        ]
        result = _require_valid_outcomes(preds_hit_miss, min_valid=20)
        assert len(result) == 20

    def test_significance_rejects_correct_incorrect(self):
        """significance.py should NOT accept correct/incorrect as valid."""
        from core.significance import _require_valid_outcomes, InsufficientOutcomes
        preds_correct = [
            {"outcome": "correct"}, {"outcome": "incorrect"},
        ]
        with pytest.raises(InsufficientOutcomes):
            _require_valid_outcomes(preds_correct, min_valid=20)

    def test_cohort_resolved_uses_hit_miss(self):
        """cohort.py get_resolved_predictions should filter on hit/miss."""
        from core.cohort import LiveForwardCohort
        import tempfile, json, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({"predictions": [
                {"outcome": "hit", "made_date": "2026-01-01", "time_horizon": "6m"},
                {"outcome": "miss", "made_date": "2026-01-01", "time_horizon": "6m"},
                {"outcome": "pending", "made_date": "2026-01-01", "time_horizon": "6m"},
            ]}, f, ensure_ascii=False)
            tmppath = f.name
        try:
            cohort = LiveForwardCohort(track_record_path=tmppath)
            resolved = cohort.get_resolved_predictions()
            assert len(resolved) == 2
            assert all(p["outcome"] in ("hit", "miss") for p in resolved)
        finally:
            os.unlink(tmppath)


class TestNoBareCorrectIncorrect:
    """Grep-based: core files should not use bare 'correct'/'incorrect' as outcome values."""

    @pytest.mark.parametrize("filepath", [
        "core/significance.py",
        "core/cohort.py",
        "core/attribution.py",
        "core/dashboard.py",
        "core/calibration.py",
    ])
    def test_no_bare_correct_in_core(self, filepath):
        """Core files should not contain 'outcome.*correct' or 'outcome.*incorrect' patterns."""
        import re
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Check for outcome == "correct" or outcome == "incorrect" patterns
        bad_patterns = [
            r'outcome\s*==\s*"correct"',
            r'outcome\s*==\s*"incorrect"',
            r'outcome.*in\s*\("correct".*"incorrect"\)',
            r'outcome.*in\s*\("incorrect".*"correct"\)',
        ]
        for pat in bad_patterns:
            matches = re.findall(pat, content)
            assert not matches, f"{filepath} contains forbidden pattern: {pat}"

    @pytest.mark.parametrize("filepath", [
        "scripts/update_outcomes.py",
        "scripts/resolve_mock_outcomes.py",
        "scripts/test_mc_rehearsal.py",
    ])
    def test_no_bare_correct_in_scripts(self, filepath):
        """Script files should not contain outcome == 'correct' or 'incorrect'."""
        import re
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        bad_patterns = [
            r'outcome\s*==\s*"correct"',
            r'outcome\s*==\s*"incorrect"',
            r'outcome.*in\s*\("correct".*"incorrect"\)',
        ]
        for pat in bad_patterns:
            matches = re.findall(pat, content)
            assert not matches, f"{filepath} contains forbidden pattern: {pat}"


class TestTrackRecordValidation:
    """Test that track_record validates outcome and direction on write."""

    def test_register_rejects_invalid_direction(self):
        from core.tools.track_record import TrackRecordManager
        import tempfile, os
        tmppath = tempfile.mktemp(suffix='.json')
        try:
            mgr = TrackRecordManager(storage_path=tmppath)
            with pytest.raises(ValueError, match="Invalid direction"):
                mgr.register_prediction(
                    asset="TEST", report_type="listed_company",
                    industry="test", direction="INVALID",
                    bold_call="test"
                )
        finally:
            if os.path.exists(tmppath):
                os.unlink(tmppath)

    def test_update_rejects_invalid_outcome(self):
        from core.tools.track_record import TrackRecordManager
        import tempfile, os
        tmppath = tempfile.mktemp(suffix='.json')
        try:
            mgr = TrackRecordManager(storage_path=tmppath)
            pred = mgr.register_prediction(
                asset="TEST", report_type="listed_company",
                industry="test", direction="bullish",
                bold_call="test"
            )
            with pytest.raises(ValueError, match="Invalid outcome"):
                mgr.update_outcome(pred.id, "correct")  # old vocab, should fail
        finally:
            if os.path.exists(tmppath):
                os.unlink(tmppath)

    def test_update_accepts_valid_outcome(self):
        from core.tools.track_record import TrackRecordManager
        import tempfile, os
        tmppath = tempfile.mktemp(suffix='.json')
        try:
            mgr = TrackRecordManager(storage_path=tmppath)
            pred = mgr.register_prediction(
                asset="TEST", report_type="listed_company",
                industry="test", direction="bullish",
                bold_call="test"
            )
            mgr.update_outcome(pred.id, "hit")
            mgr.update_outcome(pred.id, "miss")
            mgr.update_outcome(pred.id, "partial")
        finally:
            if os.path.exists(tmppath):
                os.unlink(tmppath)


class TestDashboardHtmlVocab:
    """Test that generate_dashboard_html uses unified vocab."""

    def test_dashboard_uses_hit_miss(self):
        with open("scripts/generate_dashboard_html.py", "r", encoding="utf-8") as f:
            content = f.read()
        assert '"hit"' in content
        assert '"miss"' in content
        assert 'outcome == "correct"' not in content
        assert 'outcome == "incorrect"' not in content
