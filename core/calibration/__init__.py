"""V52 Calibration — prediction backtesting dashboard + ECE/Brier metric functions.

The shadowed dead module ``core/calibration.py`` was removed in the 2026-09-06
deep-audit fix; its pure metric functions now live in ``core.calibration.metrics``.
"""

from __future__ import annotations

from core.calibration.dashboard import BiasReport, CalibrationDashboard, CalibrationSuggestion
from core.calibration.metrics import (
    compute_brier,
    compute_brier_skill_score,
    compute_ece,
    fit_logistic_recalibration,
    generate_calibration_report,
    load_and_recalibrate,
    recalibrate_confidence,
    save_calibration_report,
)

__all__ = [
    "CalibrationDashboard",
    "BiasReport",
    "CalibrationSuggestion",
    "compute_ece",
    "compute_brier",
    "compute_brier_skill_score",
    "fit_logistic_recalibration",
    "recalibrate_confidence",
    "generate_calibration_report",
    "save_calibration_report",
    "load_and_recalibrate",
]
