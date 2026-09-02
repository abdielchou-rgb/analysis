"""C5: Dimension/framework外效度归因.

Correlates prediction hit/miss with:
- SAC dimensions used
- Frameworks applied
- Report key variables

Computes IC (Information Coefficient) and attribution statistics.
"""

import json
import logging
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("2hao.attribution")


def compute_ic(
    predicted_scores: list[float],
    actual_outcomes: list[float],
) -> dict:
    """Compute Information Coefficient (rank correlation).

    IC = Spearman rank correlation between predicted scores and actual outcomes.
    High IC (>0.1) means predictions have predictive power.

    Returns: {ic, n, p_value_approx}
    """
    n = len(predicted_scores)
    if n < 10:
        return {"ic": 0, "n": n, "p_value_approx": 1.0, "error": "insufficient data"}

    # Rank data
    def rank(data):
        sorted_indices = sorted(range(len(data)), key=lambda i: data[i])
        ranks = [0.0] * len(data)
        for rank_val, idx in enumerate(sorted_indices, 1):
            ranks[idx] = rank_val
        return ranks

    rank_x = rank(predicted_scores)
    rank_y = rank(actual_outcomes)

    # Spearman IC
    mean_rx = sum(rank_x) / n
    mean_ry = sum(rank_y) / n
    cov = sum((rx - mean_rx) * (ry - mean_ry) for rx, ry in zip(rank_x, rank_y)) / n
    std_rx = math.sqrt(sum((rx - mean_rx) ** 2 for rx in rank_x) / n)
    std_ry = math.sqrt(sum((ry - mean_ry) ** 2 for ry in rank_y) / n)

    if std_rx == 0 or std_ry == 0:
        return {"ic": 0, "n": n, "p_value_approx": 1.0}

    ic = cov / (std_rx * std_ry)

    # Approximate p-value (t-test for Spearman IC)
    if abs(ic) > 0 and abs(ic) < 1:
        t_stat = ic * math.sqrt((n - 2) / (1 - ic ** 2))
        # Rough approximation: |t| > 2 ≈ p < 0.05
        p_approx = max(0.001, min(1.0, 2 * (1 - min(abs(t_stat) / 3, 1.0))))
    elif abs(ic) >= 1:
        # Perfect or near-perfect correlation
        p_approx = 0.001
    else:
        p_approx = 1.0

    return {
        "ic": round(ic, 4),
        "n": n,
        "p_value_approx": round(p_approx, 4),
        "significant": abs(ic) > 0.1 and p_approx < 0.05,
    }


def attribute_by_dimension(
    predictions: list[dict],
    dimensions: list[str] = None,
) -> dict:
    """Attribute prediction accuracy by SAC dimension.

    For each dimension, compute hit rate and IC.
    Requires predictions with 'dimensions_used' and 'outcome' fields.

    Returns: {dimension: {hit_rate, ic, count, ...}}
    """
    if not dimensions:
        dimensions = [
            "decision_gate", "core_disagreement", "business_model",
            "financial_verification", "competition", "growth",
            "governance_esg", "valuation", "catalyst", "falsification",
            "parent_subsidiary", "capital_flow", "bold_call", "risk",
        ]

    dim_stats = defaultdict(lambda: {"hits": 0, "total": 0, "scores": [], "outcomes": []})

    for p in predictions:
        if p.get("outcome") not in ("correct", "incorrect"):
            continue

        outcome_val = 1 if p["outcome"] == "correct" else 0
        used_dims = p.get("dimensions_used", [])

        for dim in used_dims:
            if dim in dimensions:
                dim_stats[dim]["total"] += 1
                dim_stats[dim]["hits"] += outcome_val
                dim_stats[dim]["scores"].append(p.get("confidence_at_make", 0.5))
                dim_stats[dim]["outcomes"].append(outcome_val)

    results = {}
    for dim, stats in dim_stats.items():
        if stats["total"] < 5:
            continue

        hit_rate = stats["hits"] / stats["total"]
        ic_result = compute_ic(stats["scores"], stats["outcomes"])

        results[dim] = {
            "hit_rate": round(hit_rate, 4),
            "ic": ic_result.get("ic", 0),
            "ic_significant": ic_result.get("significant", False),
            "count": stats["total"],
            "ic_n": ic_result.get("n", 0),
        }

    return results


def attribute_by_framework(
    predictions: list[dict],
    frameworks: list[str] = None,
) -> dict:
    """Attribute prediction accuracy by analysis framework.

    For each framework, compute hit rate and IC.
    Requires predictions with 'frameworks_used' and 'outcome' fields.

    Returns: {framework: {hit_rate, ic, count, ...}}
    """
    if not frameworks:
        frameworks = [
            "porter_five_forces", "swot", "pestel", "value_chain",
            "blue_ocean", "disruption", "moat", "financial_model",
            "dcf", "comparable", "scenario", "sotp",
        ]

    fw_stats = defaultdict(lambda: {"hits": 0, "total": 0, "scores": [], "outcomes": []})

    for p in predictions:
        if p.get("outcome") not in ("correct", "incorrect"):
            continue

        outcome_val = 1 if p["outcome"] == "correct" else 0
        used_fws = p.get("frameworks_used", [])

        for fw in used_fws:
            if fw in frameworks:
                fw_stats[fw]["total"] += 1
                fw_stats[fw]["hits"] += outcome_val
                fw_stats[fw]["scores"].append(p.get("confidence_at_make", 0.5))
                fw_stats[fw]["outcomes"].append(outcome_val)

    results = {}
    for fw, stats in fw_stats.items():
        if stats["total"] < 5:
            continue

        hit_rate = stats["hits"] / stats["total"]
        ic_result = compute_ic(stats["scores"], stats["outcomes"])

        results[fw] = {
            "hit_rate": round(hit_rate, 4),
            "ic": ic_result.get("ic", 0),
            "ic_significant": ic_result.get("significant", False),
            "count": stats["total"],
            "ic_n": ic_result.get("n", 0),
        }

    return results


def generate_attribution_report(
    predictions: list[dict],
    output_dir: str = "output",
) -> dict:
    """Generate full attribution report with dimension and framework analysis."""
    dim_attribution = attribute_by_dimension(predictions)
    fw_attribution = attribute_by_framework(predictions)

    # Overall stats
    resolved = [p for p in predictions if p.get("outcome") in ("correct", "incorrect")]
    overall_hit = sum(1 for p in resolved if p["outcome"] == "correct") / max(len(resolved), 1)

    # Find best/worst dimensions
    sorted_dims = sorted(dim_attribution.items(), key=lambda x: x[1]["hit_rate"], reverse=True)
    best_dims = sorted_dims[:3] if sorted_dims else []
    worst_dims = sorted_dims[-3:] if sorted_dims else []

    report = {
        "generated_at": datetime.now().isoformat() if hasattr(datetime, 'now') else "",
        "overall_hit_rate": round(overall_hit, 4),
        "total_predictions": len(resolved),
        "dimension_attribution": dim_attribution,
        "framework_attribution": fw_attribution,
        "best_dimensions": [{"dim": d, **s} for d, s in best_dims],
        "worst_dimensions": [{"dim": d, **s} for d, s in worst_dims],
        "interpretation": {
            "best_framework": max(fw_attribution.items(), key=lambda x: x[1]["hit_rate"])[0] if fw_attribution else "N/A",
            "worst_framework": min(fw_attribution.items(), key=lambda x: x[1]["hit_rate"])[0] if fw_attribution else "N/A",
        },
    }

    # Save report
    out_path = Path(output_dir) / "attribution_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("[ATTRIBUTION] Report saved: %s (dims=%d, frameworks=%d)",
                out_path, len(dim_attribution), len(fw_attribution))

    return report
