"""C3: Placebo/Monte Carlo significance testing (v2).

MarketSenseAI-style: generate N random portfolios/directions,
compare system performance against random baseline distribution.
Reports percentile, p-value, confidence interval, and effect size.
"""

import logging
import math
import random
from typing import Any, Optional

logger = logging.getLogger("2hao.significance")


def _effect_size_cohen_h(p1: float, p2: float) -> float:
    """Cohen's h: effect size for two proportions.

    h = 2 * (arcsin(sqrt(p1)) - arcsin(sqrt(p2)))
    Small: 0.2, Medium: 0.5, Large: 0.8
    """
    return 2 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))


def _confidence_interval(data: list[float], confidence: float = 0.95) -> tuple[float, float]:
    """Compute confidence interval for a list of values."""
    n = len(data)
    if n < 2:
        return (0, 0)
    mean = sum(data) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in data) / (n - 1))
    # z-score for 95% CI ≈ 1.96
    z = 1.96 if confidence == 0.95 else 1.645 if confidence == 0.90 else 2.576
    margin = z * std / math.sqrt(n)
    return (round(mean - margin, 4), round(mean + margin, 4))


def monte_carlo_direction_significance(
    predictions: list[dict],
    n_simulations: int = 10000,
    random_seed: int = 42,
) -> dict:
    """Test if system direction accuracy is significantly better than random.

    For each prediction with known outcome:
    1. Count system hits (correct direction)
    2. Generate N random direction assignments
    3. Compute random hit rate distribution
    4. Report system's percentile, p-value, CI, and effect size

    Args:
        predictions: List of {direction, outcome} dicts
        n_simulations: Number of random simulations (default 10000)
        random_seed: Random seed for reproducibility

    Returns:
        {system_hit_rate, random_mean, percentile, p_value, significant, ci, effect_size}
    """
    if len(predictions) < 10:
        return {
            "system_hit_rate": 0,
            "random_mean": 0.5,
            "percentile": 50,
            "p_value": 1.0,
            "significant": False,
            "error": "insufficient predictions (need >=10)",
        }

    # Filter to predictions with known outcomes
    valid = [p for p in predictions if p.get("outcome") in ("correct", "incorrect")]
    if len(valid) < 10:
        return {
            "system_hit_rate": 0,
            "random_mean": 0.5,
            "percentile": 50,
            "p_value": 1.0,
            "significant": False,
            "error": "insufficient resolved predictions (need >=10)",
        }

    n = len(valid)
    system_hits = sum(1 for p in valid if p["outcome"] == "correct")
    system_rate = system_hits / n

    # Monte Carlo: generate random direction assignments
    rng = random.Random(random_seed)
    random_hits = []
    for _ in range(n_simulations):
        # Random: each prediction has 50% chance of being "correct"
        random_correct = sum(1 for _ in range(n) if rng.random() < 0.5)
        random_hits.append(random_correct / n)

    # Compute percentile and p-value
    random_hits.sort()
    percentile = sum(1 for r in random_hits if r <= system_rate) / n_simulations * 100
    p_value = sum(1 for r in random_hits if r >= system_rate) / n_simulations

    # Confidence interval
    ci_lower, ci_upper = _confidence_interval(random_hits)

    # Effect size (Cohen's h)
    effect_size = _effect_size_cohen_h(system_rate, 0.5)

    return {
        "system_hit_rate": round(system_rate, 4),
        "system_hits": system_hits,
        "total_predictions": n,
        "random_mean": round(sum(random_hits) / len(random_hits), 4),
        "random_std": round(
            math.sqrt(sum((r - sum(random_hits)/len(random_hits))**2 for r in random_hits) / len(random_hits)), 4
        ),
        "percentile": round(percentile, 2),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
        "ci_95": (ci_lower, ci_upper),
        "effect_size_h": round(effect_size, 4),
        "effect_size_interpretation": (
            "large" if abs(effect_size) >= 0.8
            else "medium" if abs(effect_size) >= 0.5
            else "small" if abs(effect_size) >= 0.2
            else "negligible"
        ),
        "n_simulations": n_simulations,
    }


def monte_carlo_alpha_significance(
    predictions: list[dict],
    benchmark_rate: float = 0.5,
    n_simulations: int = 10000,
    random_seed: int = 42,
) -> dict:
    """Test if system alpha (excess return over benchmark) is significant.

    For directional predictions, alpha = system_rate - benchmark_rate.
    Tests if observed alpha is significantly > 0.

    Args:
        predictions: List of {direction, outcome, return_pct} dicts
        benchmark_rate: Benchmark hit rate (default 0.5 for random)
        n_simulations: Number of random simulations
        random_seed: Random seed

    Returns:
        {alpha, random_alpha_mean, percentile, p_value, significant, ci, effect_size}
    """
    valid = [p for p in predictions if p.get("outcome") in ("correct", "incorrect")]
    if len(valid) < 10:
        return {
            "alpha": 0,
            "random_alpha_mean": 0,
            "percentile": 50,
            "p_value": 1.0,
            "significant": False,
            "error": "insufficient predictions",
        }

    n = len(valid)
    system_hits = sum(1 for p in valid if p["outcome"] == "correct")
    system_rate = system_hits / n
    alpha = system_rate - benchmark_rate

    # Monte Carlo: random alpha distribution
    rng = random.Random(random_seed)
    random_alphas = []
    for _ in range(n_simulations):
        random_correct = sum(1 for _ in range(n) if rng.random() < 0.5)
        random_rate = random_correct / n
        random_alphas.append(random_rate - benchmark_rate)

    random_alphas.sort()
    percentile = sum(1 for a in random_alphas if a <= alpha) / n_simulations * 100
    p_value = sum(1 for a in random_alphas if a >= alpha) / n_simulations

    # Confidence interval for random alpha distribution
    ci_lower, ci_upper = _confidence_interval(random_alphas)

    # Effect size
    effect_size = _effect_size_cohen_h(system_rate, benchmark_rate)

    return {
        "alpha": round(alpha, 4),
        "system_rate": round(system_rate, 4),
        "benchmark_rate": benchmark_rate,
        "random_alpha_mean": round(sum(random_alphas) / len(random_alphas), 4),
        "percentile": round(percentile, 2),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
        "ci_95": (ci_lower, ci_upper),
        "effect_size_h": round(effect_size, 4),
        "n_simulations": n_simulations,
    }


def batch_significance_by_horizon(
    predictions: list[dict],
    n_simulations: int = 10000,
    random_seed: int = 42,
) -> dict:
    """Run significance tests by time horizon (6m, 12m, etc).

    Returns: {horizon: {direction_test, alpha_test, count}}
    """
    horizons = {}
    for p in predictions:
        horizon = p.get("time_horizon", "unknown")
        if horizon not in horizons:
            horizons[horizon] = []
        horizons[horizon].append(p)

    results = {}
    for horizon, preds in horizons.items():
        dir_result = monte_carlo_direction_significance(preds, n_simulations, random_seed)
        alpha_result = monte_carlo_alpha_significance(preds, n_simulations=n_simulations, random_seed=random_seed)
        results[horizon] = {
            "direction_test": dir_result,
            "alpha_test": alpha_result,
            "count": len(preds),
        }

    return results


def batch_significance_by_direction(
    predictions: list[dict],
    n_simulations: int = 10000,
    random_seed: int = 42,
) -> dict:
    """Run significance tests by direction (bullish/bearish).

    Returns: {direction: {direction_test, alpha_test, count}}
    """
    directions = {}
    for p in predictions:
        direction = p.get("direction", "unknown")
        if direction not in directions:
            directions[direction] = []
        directions[direction].append(p)

    results = {}
    for direction, preds in directions.items():
        dir_result = monte_carlo_direction_significance(preds, n_simulations, random_seed)
        alpha_result = monte_carlo_alpha_significance(preds, n_simulations=n_simulations, random_seed=random_seed)
        results[direction] = {
            "direction_test": dir_result,
            "alpha_test": alpha_result,
            "count": len(preds),
        }

    return results


def generate_significance_report(
    predictions: list[dict],
    output_dir: str = "output",
    n_simulations: int = 10000,
) -> dict:
    """Generate full significance report with direction, alpha, and batch tests."""
    dir_result = monte_carlo_direction_significance(predictions, n_simulations)
    alpha_result = monte_carlo_alpha_significance(predictions, n_simulations=n_simulations)
    by_horizon = batch_significance_by_horizon(predictions, n_simulations)
    by_direction = batch_significance_by_direction(predictions, n_simulations)

    report = {
        "direction_test": dir_result,
        "alpha_test": alpha_result,
        "by_horizon": by_horizon,
        "by_direction": by_direction,
        "interpretation": {
            "direction": (
                "系统方向判断显著优于随机（p<0.05）"
                if dir_result.get("significant")
                else "系统方向判断未达统计显著性"
            ),
            "alpha": (
                "系统alpha显著为正（p<0.05）"
                if alpha_result.get("significant")
                else "系统alpha未达统计显著性"
            ),
            "effect_size": dir_result.get("effect_size_interpretation", "unknown"),
        },
    }

    # Save report
    from pathlib import Path
    import json

    out_path = Path(output_dir) / "significance_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(
        "[SIGNIFICANCE] Direction: p=%.4f (%s), h=%.2f, Alpha: p=%.4f (%s)",
        dir_result.get("p_value", 1.0),
        "significant" if dir_result.get("significant") else "not significant",
        dir_result.get("effect_size_h", 0),
        alpha_result.get("p_value", 1.0),
        "significant" if alpha_result.get("significant") else "not significant",
    )

    return report
