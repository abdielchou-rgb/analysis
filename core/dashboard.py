"""Summary dashboard: all metrics in one view.

Aggregates calibration, significance, attribution, cohort, and pipeline
health metrics into a single JSON report.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("2hao.dashboard")


def generate_dashboard(
    output_dir: str = "output",
    track_record_path: str = "core/data/forward_picks/track_record.json",
) -> dict:
    """Generate comprehensive dashboard with all metrics.

    Returns:
        {calibration, significance, attribution, cohort, pipeline_health, generated_at}
    """
    dashboard = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "calibration": {},
        "significance": {},
        "attribution": {},
        "cohort": {},
        "pipeline_health": {},
    }

    # Load track record
    track_record_file = Path(track_record_path)
    predictions = []
    if track_record_file.exists():
        try:
            with open(track_record_file, encoding="utf-8") as f:
                data = json.load(f)
                predictions = data.get("predictions", [])
        except Exception as e:
            logger.warning("[DASHBOARD] Failed to load track record: %s", str(e))

    resolved = [p for p in predictions if p.get("outcome") in ("hit", "miss")]
    pending = [p for p in predictions if p.get("outcome") == "pending"]

    # === Calibration ===
    if resolved:
        try:
            from core.calibration.dashboard import CalibrationDashboard
            cal = CalibrationDashboard()
            dashboard["calibration"] = {
                "total_predictions": len(predictions),
                "resolved": len(resolved),
                "pending": len(pending),
                "hit_rate": round(sum(1 for p in resolved if p["outcome"] == "hit") / len(resolved), 4),
            }
        except Exception as e:
            dashboard["calibration"] = {"error": str(e)}
    else:
        dashboard["calibration"] = {"status": "no_resolved_predictions"}

    # === Significance ===
    if len(resolved) >= 10:
        try:
            from core.significance import monte_carlo_direction_significance, monte_carlo_alpha_significance
            dir_result = monte_carlo_direction_significance(resolved, n_simulations=1000)
            alpha_result = monte_carlo_alpha_significance(resolved, n_simulations=1000)
            dashboard["significance"] = {
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
        except Exception as e:
            dashboard["significance"] = {"error": str(e)}
    else:
        dashboard["significance"] = {
            "status": "insufficient_data",
            "resolved_count": len(resolved),
            "minimum_required": 10,
        }

    # === Attribution ===
    if len(resolved) >= 5:
        try:
            from core.attribution import attribute_by_dimension, attribute_by_framework
            dim_attr = attribute_by_dimension(resolved)
            fw_attr = attribute_by_framework(resolved)
            dashboard["attribution"] = {
                "dimension_attribution": dim_attr,
                "framework_attribution": fw_attr,
                "best_dimension": max(dim_attr.items(), key=lambda x: x[1]["hit_rate"])[0] if dim_attr else "N/A",
                "worst_dimension": min(dim_attr.items(), key=lambda x: x[1]["hit_rate"])[0] if dim_attr else "N/A",
            }
        except Exception as e:
            dashboard["attribution"] = {"error": str(e)}
    else:
        dashboard["attribution"] = {
            "status": "insufficient_data",
            "resolved_count": len(resolved),
            "minimum_required": 5,
        }

    # === Cohort ===
    try:
        from core.cohort import LiveForwardCohort
        cohort = LiveForwardCohort(track_record_path=track_record_path)
        cohort_stats = cohort.cohort_stats(predictions)
        expired = cohort.get_expired_predictions()
        dashboard["cohort"] = {
            "stats": cohort_stats,
            "expired_count": len(expired),
            "fixed_asset_pool_size": len(cohort.fixed_asset_pool()),
        }
    except Exception as e:
        dashboard["cohort"] = {"error": str(e)}

    # === Pipeline Health ===
    try:
        from pathlib import Path as _Path
        gate_reports = list(_Path(output_dir).glob("gate_report_*.json"))
        latest_gate = None
        if gate_reports:
            latest_gate_file = max(gate_reports, key=lambda p: p.stat().st_mtime)
            with open(latest_gate_file, encoding="utf-8") as f:
                latest_gate = json.load(f)

        dashboard["pipeline_health"] = {
            "gate_reports_count": len(gate_reports),
            "latest_gate": latest_gate,
            "fingerprint_files": len(list(_Path(output_dir).glob("*.docx"))),
        }
    except Exception as e:
        dashboard["pipeline_health"] = {"error": str(e)}

    # === Summary Stats ===
    dashboard["summary"] = {
        "total_predictions": len(predictions),
        "resolved": len(resolved),
        "pending": len(pending),
        "hit_rate": round(
            sum(1 for p in resolved if p["outcome"] == "hit") / len(resolved), 4
        ) if resolved else 0,
        "significance_achieved": dashboard.get("significance", {}).get("direction_test", {}).get("significant", False),
        "dimensions_tracked": len(dashboard.get("attribution", {}).get("dimension_attribution", {})),
        "frameworks_tracked": len(dashboard.get("attribution", {}).get("framework_attribution", {})),
    }

    # Save dashboard
    out_path = Path(output_dir) / "dashboard.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

    logger.info("[DASHBOARD] Generated: %s (predictions=%d, resolved=%d)",
                out_path, len(predictions), len(resolved))

    return dashboard


def print_dashboard_summary(dashboard: dict):
    """Print a human-readable summary of the dashboard."""
    print("=" * 60)
    print("2号分析师 Dashboard Summary")
    print("=" * 60)
    print(f"Generated: {dashboard.get('generated_at', 'N/A')}")
    print()

    # Summary
    summary = dashboard.get("summary", {})
    print(f"Total Predictions: {summary.get('total_predictions', 0)}")
    print(f"Resolved: {summary.get('resolved', 0)}")
    print(f"Pending: {summary.get('pending', 0)}")
    print(f"Hit Rate: {summary.get('hit_rate', 0):.1%}")
    print()

    # Significance
    sig = dashboard.get("significance", {})
    if "direction_test" in sig:
        dir_test = sig["direction_test"]
        print(f"Direction Significance: p={dir_test.get('p_value', 'N/A')}")
        print(f"  Significant: {dir_test.get('significant', False)}")
        print(f"  System Hit Rate: {dir_test.get('system_hit_rate', 0):.1%}")
        print(f"  Random Mean: {dir_test.get('random_mean', 0):.1%}")
    else:
        print(f"Significance: {sig.get('status', 'N/A')}")
    print()

    # Attribution
    attr = dashboard.get("attribution", {})
    if "best_dimension" in attr:
        print(f"Best Dimension: {attr['best_dimension']}")
        print(f"Worst Dimension: {attr['worst_dimension']}")
    else:
        print(f"Attribution: {attr.get('status', 'N/A')}")
    print()

    # Cohort
    cohort = dashboard.get("cohort", {})
    if "stats" in cohort:
        stats = cohort["stats"]
        print(f"Cohort: {stats.get('total', 0)} total, {stats.get('resolved', 0)} resolved")
        print(f"  Hit Rate: {stats.get('hit_rate', 0):.1%}")
    print()

    print("=" * 60)


if __name__ == "__main__":
    dashboard = generate_dashboard()
    print_dashboard_summary(dashboard)
