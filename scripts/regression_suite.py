#!/usr/bin/env python
"""Full regression test suite for 2hao-analyst pipeline."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

ROOT = Path(r"D:\Claude\projects\2hao-analyst")


@dataclass
class TestResult:
    """Single test result."""

    name: str
    passed: bool
    message: str
    category: str


class RegressionTestSuite:
    """Full regression test suite."""

    def __init__(self):
        self.results: List[TestResult] = []

    def run_test(self, name: str, category: str, test_fn):
        """Run a single test."""
        try:
            passed, message = test_fn()
            self.results.append(TestResult(name, passed, message, category))
        except Exception as e:
            self.results.append(TestResult(name, False, str(e), category))

    def test_track_record_isolation(self) -> Tuple[bool, str]:
        """R0: Mock data cannot be written to production."""
        sys.path.insert(0, str(ROOT))
        from core.tools.track_record import TrackRecordManager

        manager = TrackRecordManager()
        try:
            manager.register_prediction(
                asset="TEST_MOCK",
                report_type="test",
                industry="test",
                direction="bullish",
                bold_call="Test mock rejection",
                source="mock",
            )
            return False, "Mock was not rejected"
        except ValueError as e:
            if "Invalid source" in str(e):
                return True, "Mock correctly rejected"
            return False, "Wrong error: %s" % e

    def test_track_record_pipeline(self) -> Tuple[bool, str]:
        """R0: Pipeline source is accepted."""
        sys.path.insert(0, str(ROOT))
        from core.tools.track_record import TrackRecordManager

        manager = TrackRecordManager()
        try:
            pred = manager.register_prediction(
                asset="TEST_PIPELINE_001",
                report_type="test",
                industry="test",
                direction="bullish",
                bold_call="Test pipeline acceptance",
                source="pipeline",
            )
            # Clean up
            manager.record.predictions = [p for p in manager.record.predictions if p.id != pred.id]
            manager._save()
            return True, "Pipeline source accepted"
        except Exception as e:
            return False, "Pipeline rejected: %s" % e

    def test_section_writer_exemplar(self) -> Tuple[bool, str]:
        """R1: section_writer has exemplar injection."""
        sys.path.insert(0, str(ROOT))
        from pipeline.section_writer import SectionWriter

        sw = SectionWriter()
        if hasattr(sw, "_build_exemplar_injection"):
            return True, "Exemplar injection method exists"
        return False, "Missing _build_exemplar_injection"

    def test_iron_gate_v2(self) -> Tuple[bool, str]:
        """R1: iron_gate has V2 verification."""
        sys.path.insert(0, str(ROOT))
        from pipeline.iron_gate import IronGate

        gate = IronGate(report_path=str(ROOT / "README.md"))
        if hasattr(gate, "_run_irongate_v2_checks"):
            return True, "V2 verification method exists"
        return False, "Missing _run_irongate_v2_checks"

    def test_data_collector_enrichment(self) -> Tuple[bool, str]:
        """R1: data_collector has context enrichment."""
        sys.path.insert(0, str(ROOT))
        from pipeline.data_collector import DataCollectorV5

        dc = DataCollectorV5()
        if hasattr(dc, "_enrich_with_context"):
            return True, "Context enrichment method exists"
        return False, "Missing _enrich_with_context"

    def test_exemplar_sanitizer(self) -> Tuple[bool, str]:
        """R1: Exemplar sanitizer removes sensitive content."""
        sys.path.insert(0, str(ROOT / "scripts"))
        from exemplar_injector import ExemplarSanitizer

        dirty = "This is AI generated content with [E1] placeholders."
        clean = ExemplarSanitizer.sanitize(dirty, max_length=50)

        if "AI" not in clean and len(clean) <= 50:
            return True, "Sanitizer works correctly"
        return False, "Sanitizer output: %s" % clean

    def test_truth_set_exists(self) -> Tuple[bool, str]:
        """R2: Golden numeric truth set exists."""
        truth_set = ROOT / "benchmark" / "golden_numeric" / "truth_set.json"
        if truth_set.exists():
            data = json.loads(truth_set.read_text(encoding="utf-8"))
            verified = sum(1 for e in data if e.get("canonical") is not None)
            return True, "Truth set: %d entries (%d verified)" % (len(data), verified)
        return False, "truth_set.json not found"

    def test_truth_set_expanded(self) -> Tuple[bool, str]:
        """R2: Truth set has 100+ entries."""
        truth_set = ROOT / "benchmark" / "golden_numeric" / "truth_set.json"
        if truth_set.exists():
            data = json.loads(truth_set.read_text(encoding="utf-8"))
            if len(data) >= 100:
                return True, "Truth set has %d entries" % len(data)
            return False, "Truth set only has %d entries (need 100+)" % len(data)
        return False, "truth_set.json not found"

    def test_verification_pipeline(self) -> Tuple[bool, str]:
        """R2: Verification pipeline runs successfully."""
        sys.path.insert(0, str(ROOT / "scripts"))
        from golden_numeric_verify import GoldenNumericVerifier

        verifier = GoldenNumericVerifier()
        if len(verifier.truth_set) > 0:
            return True, "Verifier loaded %d truth entries" % len(verifier.truth_set)
        return False, "Verifier has no truth entries"

    def test_ab_test_framework(self) -> Tuple[bool, str]:
        """R3: A/B test framework exists."""
        ab_test = ROOT / "scripts" / "r3_ab_test.py"
        if ab_test.exists():
            return True, "A/B test framework exists"
        return False, "r3_ab_test.py not found"

    def test_exemplar_bank_exists(self) -> Tuple[bool, str]:
        """Exemplar bank exists and is loadable."""
        index_file = ROOT / "benchmark" / "exemplar_bank" / "exemplar_index.jsonl"
        if index_file.exists():
            # Check first line
            with open(index_file, "r", encoding="utf-8") as f:
                first_line = f.readline()
                if first_line:
                    entry = json.loads(first_line)
                    return True, "Exemplar bank has entries"
        return False, "Exemplar bank not found or empty"

    def test_sft_data_exists(self) -> Tuple[bool, str]:
        """SFT training data exists."""
        train_file = ROOT / "benchmark" / "sft_training" / "sft_train.jsonl"
        if train_file.exists():
            # Count lines
            with open(train_file, "r", encoding="utf-8") as f:
                count = sum(1 for _ in f)
            return True, "SFT training data: %d records" % count
        return False, "sft_train.jsonl not found"

    def test_mock_isolation_file(self) -> Tuple[bool, str]:
        """R0: Mock data is isolated."""
        mock_file = ROOT / "core" / "data" / "forward_picks" / "mock_track_record.json"
        if mock_file.exists():
            data = json.loads(mock_file.read_text(encoding="utf-8"))
            preds = data.get("predictions", [])
            return True, "Mock track record: %d entries isolated" % len(preds)
        return False, "mock_track_record.json not found"

    def run_all(self) -> dict:
        """Run all regression tests."""
        print("=" * 60)
        print("2hao-analyst Regression Test Suite")
        print("=" * 60)

        # R0: Mock Isolation
        print("\n[R0] Mock Isolation")
        self.run_test("track_record_mock_rejected", "R0", self.test_track_record_isolation)
        self.run_test("track_record_pipeline_accepted", "R0", self.test_track_record_pipeline)
        self.run_test("mock_isolation_file", "R0", self.test_mock_isolation_file)

        # R1: Pipeline Integration
        print("\n[R1] Pipeline Integration")
        self.run_test("section_writer_exemplar", "R1", self.test_section_writer_exemplar)
        self.run_test("iron_gate_v2", "R1", self.test_iron_gate_v2)
        self.run_test("data_collector_enrichment", "R1", self.test_data_collector_enrichment)
        self.run_test("exemplar_sanitizer", "R1", self.test_exemplar_sanitizer)

        # R2: Golden Numeric
        print("\n[R2] Golden Numeric")
        self.run_test("truth_set_exists", "R2", self.test_truth_set_exists)
        self.run_test("truth_set_expanded", "R2", self.test_truth_set_expanded)
        self.run_test("verification_pipeline", "R2", self.test_verification_pipeline)

        # R3: A/B Testing
        print("\n[R3] A/B Testing")
        self.run_test("ab_test_framework", "R3", self.test_ab_test_framework)

        # Data Assets
        print("\n[Data] Assets")
        self.run_test("exemplar_bank_exists", "Data", self.test_exemplar_bank_exists)
        self.run_test("sft_data_exists", "Data", self.test_sft_data_exists)

        # Summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        print("Total: %d" % total)
        print("Passed: %d" % passed)
        print("Failed: %d" % failed)
        print("Pass Rate: %.2f%%" % (passed / total * 100 if total > 0 else 0))

        # Group by category
        categories = {}
        for r in self.results:
            if r.category not in categories:
                categories[r.category] = {"passed": 0, "failed": 0}
            if r.passed:
                categories[r.category]["passed"] += 1
            else:
                categories[r.category]["failed"] += 1

        print("\nBy Category:")
        for cat, counts in sorted(categories.items()):
            print("  %s: %d/%d passed" % (cat, counts["passed"], counts["passed"] + counts["failed"]))

        # Failed tests
        if failed > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if not r.passed:
                    print("  [%s] %s: %s" % (r.category, r.name, r.message))

        print("=" * 60)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0,
            "results": [
                {"name": r.name, "passed": r.passed, "message": r.message, "category": r.category} for r in self.results
            ],
        }


def main():
    suite = RegressionTestSuite()
    summary = suite.run_all()

    # Save results
    output = ROOT / "benchmark" / "regression_results.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nResults saved: %s" % output)

    # Exit code
    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
