"""C3: Placebo/Monte Carlo significance testing.

MarketSenseAI-style: generate N random portfolios/directions,
compare system performance against random baseline distribution.
Reports percentile and p-value.
"""

import logging
import math
import random
from typing import Any

logger = logging.getLogger("2hao.significance")


def monte_carlo_direction_significance(
    predictions: list[dict],
    n_simulations: int = 1000,
    random_seed: int = 42,
) -> dict:
    """Test if system direction accuracy is significantly better than random.

    For each prediction with known outcome:
    1. Count system hits (correct direction)
    2. Generate N random direction assignments
    3. Compute random hit rate distribution
    4. Report system's percentile and p-value

    Args:
        predictions: List of {direction, outcome} dicts
        n_simulations: Number of random simulations (default 1000)
        random_seed: Random seed for reproducibility

    Returns:
        {system_hit_rate, random_mean, percentile, p_value, significant}
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
        "n_simulations": n_simulations,
    }


def monte_carlo_alpha_significance(
    predictions: list[dict],
    benchmark_rate: float = 0.5,
    n_simulations: int = 1000,
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
        {alpha, random_alpha_mean, percentile, p_value, significant}
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

    return {
        "alpha": round(alpha, 4),
        "system_rate": round(system_rate, 4),
        "benchmark_rate": benchmark_rate,
        "random_alpha_mean": round(sum(random_alphas) / len(random_alphas), 4),
        "percentile": round(percentile, 2),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
        "n_simulations": n_simulations,
    }


def generate_significance_report(
    predictions: list[dict],
    output_dir: str = "output",
) -> dict:
    """Generate full significance report with direction and alpha tests."""
    dir_result = monte_carlo_direction_significance(predictions)
    alpha_result = monte_carlo_alpha_significance(predictions)

    report = {
        "direction_test": dir_result,
        "alpha_test": alpha_result,
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
        "[SIGNIFICANCE] Direction: p=%.4f (%s), Alpha: p=%.4f (%s)",
        dir_result.get("p_value", 1.0),
        "significant" if dir_result.get("significant") else "not significant",
        alpha_result.get("p_value", 1.0),
        "significant" if alpha_result.get("significant") else "not significant",
    )

    return report
