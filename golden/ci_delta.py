#!/usr/bin/env python3
"""A5: CI delta script — compare Gate scores against golden truth set.

Usage:
    python golden/ci_delta.py [--golden golden/golden_set.json] [--result output/result.json]

Compares current run results against golden truth set.
Reports:
    - Total score delta (current vs golden baseline)
    - Per-category delta
    - Regression alerts (delta > threshold)
"""

import json
import sys
from pathlib import Path
from typing import Any

GOLDEN_VERSION = "v2026-09-02"
DELTA_THRESHOLD = 0.01  # 1% regression triggers alert
CATEGORY_DELTA_THRESHOLD = 0.05  # 5% per-category regression


def load_golden(path: str = "golden/golden_set.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_gate_result(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_case(case: dict, gate_result: dict) -> dict:
    """Evaluate a single golden case against gate result."""
    result = {
        "id": case["id"],
        "asset": case["asset"],
        "category": case["category"],
        "field": case["field"],
        "passed": False,
        "expected": case.get("expected_value") or case.get("expected_range"),
        "actual": None,
        "delta": None,
    }

    checks = gate_result.get("checks", [])
    check_map = {c["name"]: c for c in checks}

    # Match golden case to gate check
    field = case["field"]
    if field in check_map:
        check = check_map[field]
        result["actual"] = check.get("score", 0)
        result["passed"] = check.get("passed", False)
    elif case["category"] == "consistency":
        # Consistency checks are aggregate
        consistency_checks = [c for c in checks if "consistency" in c["name"]]
        if consistency_checks:
            avg_score = sum(c.get("score", 0) for c in consistency_checks) / len(consistency_checks)
            result["actual"] = avg_score
            result["passed"] = all(c.get("passed", False) for c in consistency_checks)
    elif case["category"] == "format":
        format_checks = [c for c in checks if any(k in c["name"] for k in ["placeholder", "forbidden", "aigc"])]
        if format_checks:
            result["actual"] = sum(1 for c in format_checks if c.get("passed", False)) / len(format_checks)
            result["passed"] = result["actual"] >= 0.8

    # Check range
    if case.get("expected_range") and result["actual"] is not None:
        lo, hi = case["expected_range"]
        result["passed"] = lo <= result["actual"] <= hi

    return result


def compute_delta(results: list[dict], baseline: dict = None) -> dict:
    """Compute aggregate delta between current results and baseline."""
    if not baseline:
        baseline = {"overall_score": 0.87, "category_scores": {}}

    current_scores = {}
    for r in results:
        cat = r["category"]
        if cat not in current_scores:
            current_scores[cat] = []
        if r["actual"] is not None:
            current_scores[cat].append(r["actual"])

    category_deltas = {}
    for cat, scores in current_scores.items():
        avg = sum(scores) / len(scores) if scores else 0
        base = baseline.get("category_scores", {}).get(cat, avg)
        category_deltas[cat] = {
            "current": round(avg, 4),
            "baseline": round(base, 4),
            "delta": round(avg - base, 4),
            "regression": (avg - base) < -DELTA_THRESHOLD,
        }

    overall_current = sum(r["actual"] for r in results if r["actual"] is not None) / max(
        sum(1 for r in results if r["actual"] is not None), 1
    )
    overall_baseline = baseline.get("overall_score", 0.87)
    overall_delta = overall_current - overall_baseline

    return {
        "golden_version": GOLDEN_VERSION,
        "total_cases": len(results),
        "passed_cases": sum(1 for r in results if r["passed"]),
        "overall_current": round(overall_current, 4),
        "overall_baseline": overall_baseline,
        "overall_delta": round(overall_delta, 4),
        "regression": overall_delta < -DELTA_THRESHOLD,
        "category_deltas": category_deltas,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Golden truth set CI delta checker")
    parser.add_argument("--golden", default="golden/golden_set.json", help="Path to golden set")
    parser.add_argument("--result", default=None, help="Path to gate result JSON (optional)")
    parser.add_argument("--baseline", default=None, help="Path to baseline JSON (optional)")
    args = parser.parse_args()

    golden = load_golden(args.golden)
    cases = golden.get("cases", [])

    # Load gate result if provided
    gate_result = {}
    if args.result:
        gate_result = load_gate_result(args.result)

    # Evaluate all cases
    results = [evaluate_case(case, gate_result) for case in cases]

    # Load baseline
    baseline = None
    if args.baseline:
        with open(args.baseline, encoding="utf-8") as f:
            baseline = json.load(f)

    # Compute delta
    delta = compute_delta(results, baseline)

    # Print report
    print(f"\n{'='*60}")
    print(f"Golden Truth Set CI Delta Report")
    print(f"Version: {delta['golden_version']}")
    print(f"{'='*60}")
    print(f"Total cases: {delta['total_cases']}")
    print(f"Passed: {delta['passed_cases']}")
    print(f"Overall score: {delta['overall_current']:.4f} (baseline: {delta['overall_baseline']:.4f})")
    print(f"Overall delta: {delta['overall_delta']:+.4f}")
    print(f"Regression: {'YES' if delta['regression'] else 'NO'}")
    print(f"\nCategory breakdown:")
    for cat, info in delta["category_deltas"].items():
        status = "REGRESSION" if info["regression"] else "OK"
        print(f"  {cat}: {info['current']:.4f} (baseline: {info['baseline']:.4f}, delta: {info['delta']:+.4f}) [{status}]")

    # Exit code: 1 if regression
    if delta["regression"]:
        print(f"\n*** CI FAIL: Overall regression detected (delta={delta['overall_delta']:+.4f}) ***")
        sys.exit(1)
    else:
        print(f"\n*** CI PASS ***")
        sys.exit(0)


if __name__ == "__main__":
    main()
