"""CLI dashboard tool.

Quick access to pipeline metrics from command line.
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(
        description="2号分析师 Dashboard CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.dashboard                    # Show full dashboard
  python -m scripts.dashboard --significance     # Show significance only
  python -m scripts.dashboard --cohort           # Show cohort stats
  python -m scripts.dashboard --update-outcomes  # Update prediction outcomes
  python -m scripts.dashboard --validate-golden  # Validate against golden set
  python -m scripts.dashboard --export           # Export all reports
        """,
    )

    parser.add_argument("--significance", action="store_true", help="Show significance tests")
    parser.add_argument("--cohort", action="store_true", help="Show cohort statistics")
    parser.add_argument("--attribution", action="store_true", help="Show dimension/framework attribution")
    parser.add_argument("--calibration", action="store_true", help="Show calibration metrics")
    parser.add_argument("--update-outcomes", action="store_true", help="Update prediction outcomes")
    parser.add_argument("--validate-golden", action="store_true", help="Validate against golden set")
    parser.add_argument("--export", action="store_true", help="Export all reports")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output-dir", default="output", help="Output directory")

    args = parser.parse_args()

    # Default to full dashboard if no specific option
    show_all = not any([
        args.significance, args.cohort, args.attribution, args.calibration,
        args.update_outcomes, args.validate_golden, args.export,
    ])

    if args.update_outcomes:
        from scripts.update_outcomes import run_outcome_update
        stats = run_outcome_update(dry_run=False)
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print(f"Outcome Update: {stats['updated']} resolved, {stats['pending_review']} pending review")
        return

    if args.validate_golden:
        from scripts.validate_golden import run_golden_validation
        results = run_golden_validation(args.output_dir)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for name, result in results.items():
                delta = result.get("delta", {})
                print(f"{name}: combined={delta.get('combined_vs_best', 0):.2%}")
        return

    if args.export:
        from core.dashboard import generate_dashboard
        dashboard = generate_dashboard(args.output_dir)
        print(f"Dashboard exported to {args.output_dir}/dashboard.json")
        return

    # Show dashboard sections
    from core.dashboard import generate_dashboard, print_dashboard_summary

    dashboard = generate_dashboard(args.output_dir)

    if args.json:
        print(json.dumps(dashboard, indent=2))
        return

    if args.significance:
        sig = dashboard.get("significance", {})
        print("=== Significance Tests ===")
        if "direction_test" in sig:
            dt = sig["direction_test"]
            print(f"Direction: p={dt.get('p_value', 'N/A')}, significant={dt.get('significant', False)}")
            print(f"  System: {dt.get('system_hit_rate', 0):.1%}, Random: {dt.get('random_mean', 0):.1%}")
            print(f"  Effect size: {dt.get('effect_size_h', 0):.2f} ({dt.get('effect_size_interpretation', 'N/A')})")
        else:
            print(f"  Status: {sig.get('status', 'N/A')}")
        return

    if args.cohort:
        cohort = dashboard.get("cohort", {})
        print("=== Cohort Statistics ===")
        if "stats" in cohort:
            stats = cohort["stats"]
            print(f"Total: {stats.get('total', 0)}, Resolved: {stats.get('resolved', 0)}")
            print(f"Hit Rate: {stats.get('hit_rate', 0):.1%}")
            print(f"Fixed Asset Pool: {cohort.get('fixed_asset_pool_size', 0)}")
        return

    if args.attribution:
        attr = dashboard.get("attribution", {})
        print("=== Attribution ===")
        if "best_dimension" in attr:
            print(f"Best: {attr['best_dimension']}, Worst: {attr['worst_dimension']}")
        for dim, stats in attr.get("dimension_attribution", {}).items():
            print(f"  {dim}: hit_rate={stats.get('hit_rate', 0):.1%}, ic={stats.get('ic', 0):.3f}")
        return

    if args.calibration:
        cal = dashboard.get("calibration", {})
        print("=== Calibration ===")
        print(f"Total: {cal.get('total_predictions', 0)}, Resolved: {cal.get('resolved', 0)}")
        print(f"Hit Rate: {cal.get('hit_rate', 0):.1%}")
        return

    # Full dashboard
    print_dashboard_summary(dashboard)


if __name__ == "__main__":
    main()
