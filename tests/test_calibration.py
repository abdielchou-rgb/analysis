"""Tests for CalibrationDashboard."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.calibration import BiasReport, CalibrationDashboard, CalibrationSuggestion
from core.calibration.dashboard import SectorAccuracy, TimeframeAccuracy, ValuationBias


def test_dashboard_instantiates():
    db = CalibrationDashboard()
    assert db is not None


def test_accuracy_by_sector():
    db = CalibrationDashboard()
    result = db.accuracy_by_sector()
    assert isinstance(result, list)
    for r in result:
        assert isinstance(r, SectorAccuracy)


def test_accuracy_by_timeframe():
    db = CalibrationDashboard()
    result = db.accuracy_by_timeframe()
    assert isinstance(result, list)
    for r in result:
        assert isinstance(r, TimeframeAccuracy)


def test_systematic_bias():
    db = CalibrationDashboard()
    result = db.systematic_bias()
    assert isinstance(result, BiasReport)


def test_valuation_bias():
    db = CalibrationDashboard()
    result = db.valuation_bias()
    assert isinstance(result, ValuationBias)


def test_full_report():
    db = CalibrationDashboard()
    report = db.full_report()
    assert isinstance(report, str)
    assert len(report) > 0


def test_suggest_calibration():
    db = CalibrationDashboard()
    suggestions = db.suggest_calibration()
    assert isinstance(suggestions, list)
    for s in suggestions:
        assert isinstance(s, CalibrationSuggestion)
        assert s.area


if __name__ == "__main__":
    test_dashboard_instantiates()
    test_accuracy_by_sector()
    test_accuracy_by_timeframe()
    test_systematic_bias()
    test_valuation_bias()
    test_full_report()
    test_suggest_calibration()
    print("All calibration tests passed")
