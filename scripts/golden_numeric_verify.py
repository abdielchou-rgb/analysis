#!/usr/bin/env python
"""Golden Numeric Verification Pipeline - CI Ready."""

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
TRUTH_SET = ROOT / "benchmark" / "golden_numeric" / "truth_set.json"
RESULTS_DIR = ROOT / "benchmark" / "golden_numeric" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class VerificationResult:
    """Single verification result."""

    asset: str
    field: str
    expected: float
    actual: float
    tolerance: float
    passed: bool
    error_pct: float
    source: str


@dataclass
class VerificationReport:
    """Full verification report."""

    timestamp: str
    total: int
    passed: int
    failed: int
    skipped: int
    pass_rate: float
    results: List[VerificationResult]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "pass_rate": "%.2f%%" % (self.pass_rate * 100),
            },
            "results": [
                {
                    "asset": r.asset,
                    "field": r.field,
                    "expected": r.expected,
                    "actual": r.actual,
                    "tolerance": r.tolerance,
                    "passed": r.passed,
                    "error_pct": "%.2f%%" % (r.error_pct * 100),
                }
                for r in self.results
            ],
        }


class GoldenNumericVerifier:
    """Verify report outputs against golden numeric truth set."""

    def __init__(self):
        self.truth_set = self._load_truth_set()

    def _load_truth_set(self) -> List[dict]:
        """Load truth set from disk."""
        if not TRUTH_SET.exists():
            print("ERROR: truth_set.json not found")
            return []

        data = json.loads(TRUTH_SET.read_text(encoding="utf-8"))
        # Filter to verified entries only
        return [e for e in data if e.get("canonical") is not None]

    def extract_numeric(self, report_text: str, field: str) -> float:
        """Extract numeric value from report text."""
        import re

        # Field-specific patterns
        patterns = {
            "target_price": [
                r"目标价[^\d]*?(\d+\.?\d*)",
                r"target\s*price[^\d]*?(\d+\.?\d*)",
                r"予.*?(\d+\.?\d*).*?元.*?目标",
            ],
            "pe_ratio": [
                r"PE[^\d]*?(\d+\.?\d*)",
                r"市盈率[^\d]*?(\d+\.?\d*)",
                r"(\d+\.?\d*)\s*倍.*?PE",
            ],
            "revenue": [
                r"营[业收]入[^\d]*?(\d+\.?\d*)\s*[亿万]",
                r"revenue[^\d]*?(\d+\.?\d*)",
            ],
            "eps": [
                r"每股收益[^\d]*?(\d+\.?\d*)",
                r"EPS[^\d]*?(\d+\.?\d*)",
            ],
            "roe": [
                r"ROE[^\d]*?(\d+\.?\d*)",
                r"净资产收益率[^\d]*?(\d+\.?\d*)",
            ],
        }

        field_patterns = patterns.get(field, [])
        for pattern in field_patterns:
            match = re.search(pattern, report_text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, IndexError):
                    continue

        return None

    def verify_single(self, entry: dict, report_text: str) -> VerificationResult:
        """Verify a single truth entry against report."""
        expected = entry["canonical"]
        actual = self.extract_numeric(report_text, entry["field"])
        tolerance = entry.get("tolerance", 0.05)

        if actual is None:
            return VerificationResult(
                asset=entry["asset"],
                field=entry["field"],
                expected=expected,
                actual=None,
                tolerance=tolerance,
                passed=False,
                error_pct=100.0,
                source="not_found",
            )

        # Calculate error
        if expected != 0:
            error_pct = abs(actual - expected) / abs(expected) * 100
        else:
            error_pct = 0.0 if actual == 0 else 100.0

        passed = error_pct <= (tolerance * 100)

        return VerificationResult(
            asset=entry["asset"],
            field=entry["field"],
            expected=expected,
            actual=actual,
            tolerance=tolerance,
            passed=passed,
            error_pct=error_pct,
            source="extracted",
        )

    def verify_report(
        self,
        report_text: str,
        asset_filter: str = None,
    ) -> VerificationReport:
        """Verify a report against all applicable truth entries."""
        results = []

        for entry in self.truth_set:
            if asset_filter and entry["asset"] != asset_filter:
                continue
            result = self.verify_single(entry, report_text)
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed and r.actual is not None)
        skipped = sum(1 for r in results if r.actual is None)
        total = len(results)

        return VerificationReport(
            timestamp=datetime.now().isoformat(),
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            pass_rate=passed / total if total > 0 else 0.0,
            results=results,
        )

    def save_report(self, report: VerificationReport, name: str = None):
        """Save verification report to disk."""
        if name is None:
            name = "verify_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S")

        output = RESULTS_DIR / name
        output.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print("Report saved: %s" % output)
        return output


def main():
    """Main entry point for CI."""
    print("=" * 60)
    print("Golden Numeric Verification Pipeline")
    print("=" * 60)

    verifier = GoldenNumericVerifier()

    if not verifier.truth_set:
        print("ERROR: No verified truth entries found")
        sys.exit(1)

    print("Truth set: %d verified entries" % len(verifier.truth_set))

    # For CI: verify a sample report or synthetic test
    # In production, this would receive actual report text

    # Create a synthetic test report
    test_report = """
    贵州茅台（600519）深度研究

    目标价：1800元，维持买入评级。

    2024年营业收入预计达到1500亿元，同比增长15%。
    每股收益预计为60元，对应PE倍数30倍。
    ROE维持在30%以上。
    """

    print("\nVerifying test report...")
    report = verifier.verify_report(test_report, asset_filter="贵州茅台")

    print("\n" + "=" * 60)
    print("Verification Results")
    print("=" * 60)
    print("Total: %d" % report.total)
    print("Passed: %d" % report.passed)
    print("Failed: %d" % report.failed)
    print("Skipped: %d" % report.skipped)
    print("Pass Rate: %.2f%%" % (report.pass_rate * 100))

    # Save report
    verifier.save_report(report)

    # Exit code for CI
    if report.pass_rate >= 0.5:
        print("\nCI: PASS")
        sys.exit(0)
    else:
        print("\nCI: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
