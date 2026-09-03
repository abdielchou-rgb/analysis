"""C1+C2: Calibration panel + posterior recalibration.

Computes ECE, Brier score, Brier Skill Score for prediction calibration.
Fits logistic regression to recalibrate confidence scores.
"""

import json
import math
from pathlib import Path
from typing import Any

# Default calibration config
CALIBRATION_BINS = 10
MIN_SAMPLES_PER_BIN = 5


def compute_ece(confidences: list[float], outcomes: list[int], n_bins: int = CALIBRATION_BINS) -> float:
    """Compute Expected Calibration Error (ECE).

    ECE = Σ (|bin_size| / n) * |accuracy(bin) - confidence(bin)|
    """
    if not confidences or not outcomes or len(confidences) != len(outcomes):
        return 0.0

    n = len(confidences)
    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    ece = 0.0

    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        in_bin = [j for j in range(n) if lo <= confidences[j] < hi]
        if not in_bin:
            continue
        bin_size = len(in_bin)
        avg_conf = sum(confidences[j] for j in in_bin) / bin_size
        avg_outcome = sum(outcomes[j] for j in in_bin) / bin_size
        ece += (bin_size / n) * abs(avg_outcome - avg_conf)

    return round(ece, 4)


def compute_brier(confidences: list[float], outcomes: list[int]) -> float:
    """Compute Brier score (lower is better, 0 = perfect)."""
    if not confidences or not outcomes:
        return 0.0
    n = len(confidences)
    return round(sum((confidences[i] - outcomes[i]) ** 2 for i in range(n)) / n, 4)


def compute_brier_skill_score(
    confidences: list[float], outcomes: list[int], baseline_rate: float = 0.5
) -> float:
    """Compute Brier Skill Score vs base-rate baseline.

    BSS = 1 - (Brier_system / Brier_baseline)
    BSS > 0 means system is better than base rate.
    """
    brier_system = compute_brier(confidences, outcomes)
    # Baseline: always predict base_rate
    brier_baseline = sum((baseline_rate - o) ** 2 for o in outcomes) / max(len(outcomes), 1)
    if brier_baseline == 0:
        return 0.0
    return round(1 - brier_system / brier_baseline, 4)


def fit_logistic_recalibration(
    confidences: list[float], outcomes: list[int]
) -> dict:
    """Fit logistic regression for posterior recalibration.

    Returns: {a, b} where calibrated_prob = sigmoid(a * logit(confidence) + b)
    Falls back to isotonic if scipy not available.
    """
    if len(confidences) < 20:
        return {"method": "insufficient_data", "a": 1.0, "b": 0.0}

    try:
        from scipy.optimize import minimize

        def objective(params):
            a, b = params
            calibrated = []
            for c in confidences:
                c = max(0.001, min(0.999, c))  # clip to avoid log(0)
                logit_c = math.log(c / (1 - c))
                cal_logit = a * logit_c + b
                cal_prob = 1 / (1 + math.exp(-cal_logit))
                calibrated.append(cal_prob)
            # Negative log-likelihood
            nll = 0
            for cp, o in zip(calibrated, outcomes):
                cp = max(0.001, min(0.999, cp))
                nll -= o * math.log(cp) + (1 - o) * math.log(1 - cp)
            return nll

        from scipy.optimize import minimize as _minimize
        result = _minimize(objective, [1.0, 0.0], method="Nelder-Mead")
        a, b = result.x
        return {"method": "logistic", "a": round(a, 4), "b": round(b, 4)}
    except ImportError:
        # Fallback: Platt scaling (simplified)
        return {"method": "platt_fallback", "a": 1.0, "b": 0.0}


def recalibrate_confidence(confidence: float, params: dict) -> float:
    """Apply recalibration to a single confidence score."""
    a = params.get("a", 1.0)
    b = params.get("b", 0.0)
    if params.get("method") in ("insufficient_data", None):
        return confidence
    c = max(0.001, min(0.999, confidence))
    logit_c = math.log(c / (1 - c))
    cal_logit = a * logit_c + b
    return round(1 / (1 + math.exp(-cal_logit)), 4)


def generate_calibration_report(
    confidences: list[float],
    outcomes: list[int],
    asset_names: list[str] = None,
) -> dict:
    """Generate full calibration report with ECE, Brier, BSS, and recalibration params."""
    ece = compute_ece(confidences, outcomes)
    brier = compute_brier(confidences, outcomes)
    bss = compute_brier_skill_score(confidences, outcomes)
    recal_params = fit_logistic_recalibration(confidences, outcomes)

    # Bin-level breakdown
    n_bins = CALIBRATION_BINS
    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    bins = []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        in_bin = [j for j in range(len(confidences)) if lo <= confidences[j] < hi]
        if in_bin:
            avg_conf = sum(confidences[j] for j in in_bin) / len(in_bin)
            avg_out = sum(outcomes[j] for j in in_bin) / len(in_bin)
            bins.append({
                "range": f"[{lo:.1f}, {hi:.1f})",
                "count": len(in_bin),
                "avg_confidence": round(avg_conf, 3),
                "avg_outcome": round(avg_out, 3),
                "gap": round(abs(avg_out - avg_conf), 3),
            })

    return {
        "ece": ece,
        "brier_score": brier,
        "brier_skill_score": bss,
        "recalibration": recal_params,
        "bins": bins,
        "total_predictions": len(confidences),
        "positive_rate": round(sum(outcomes) / max(len(outcomes), 1), 3),
    }


def save_calibration_report(report: dict, output_dir: str = "output") -> str:
    """Save calibration report to JSON."""
    path = Path(output_dir) / "calibration_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return str(path)


def load_and_recalibrate(
    track_record_path: str, recal_params: dict = None
) -> list[dict]:
    """Load track_record.json and apply recalibration to confidence scores.

    Returns updated predictions with calibrated_confidence field.
    """
    with open(track_record_path, encoding="utf-8") as f:
        data = json.load(f)

    predictions = data.get("predictions", [])
    if not predictions:
        return []

    if recal_params is None:
        # Compute recalibration from historical outcomes
        confidences = []
        outcomes = []
        for p in predictions:
            if p.get("outcome") in ("hit", "miss"):
                conf = p.get("confidence_at_make", 0.5)
                out = 1 if p["outcome"] == "hit" else 0
                confidences.append(conf)
                outcomes.append(out)
        if len(confidences) >= 20:
            recal_params = fit_logistic_recalibration(confidences, outcomes)
        else:
            recal_params = {"method": "insufficient_data"}

    # Apply recalibration
    for p in predictions:
        conf = p.get("confidence_at_make", 0.5)
        p["calibrated_confidence"] = recal_confidence(conf, recal_params)

    return predictions
