"""S1-1/S1-3/S1-4: Prediction pipeline tests."""

import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def test_prediction_daily_import():
    from scripts.prediction_daily import main

    assert callable(main)


def test_prediction_attribution_import():
    from scripts.prediction_attribution import attribute

    assert callable(attribute)


def test_prediction_monthly_import():
    from scripts.prediction_monthly import generate_monthly_report

    assert callable(generate_monthly_report)


def test_benchmark_client_import():
    from core.benchmark_client import get_index_nav_series

    assert callable(get_index_nav_series)


@dataclass
class _FakePick:
    verification_status: str = "miss"
    direction: str = "bull"
    actual_return: float = 0.0
    base_target: float = 0.2
    confidence: float = 0.8
    core_thesis: str = "test"


def test_attribution_direction_error():
    from scripts.prediction_attribution import attribute

    pick = _FakePick(direction="bull", actual_return=-0.15, verification_status="miss")
    result = attribute(pick)
    assert result["tag"] == "direction_wrong"


def test_attribution_magnitude_error():
    from scripts.prediction_attribution import attribute

    pick = _FakePick(direction="bull", actual_return=0.03, base_target=0.30, verification_status="miss")
    result = attribute(pick)
    assert result["tag"] in ("magnitude_small", "timing_off")


def test_attribution_hit():
    from scripts.prediction_attribution import attribute

    pick = _FakePick(verification_status="hit")
    result = attribute(pick)
    assert result is None
