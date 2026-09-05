#!/usr/bin/env python
"""End-to-end pipeline smoke test (no network required)."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
sys.path.insert(0, str(ROOT))


def test_full_pipeline():
    """Test the full pipeline end-to-end."""
    print("=" * 60)
    print("End-to-End Pipeline Smoke Test")
    print("=" * 60)

    results = []

    # 1. Test data collection (mock)
    print("\n[1] Data Collection")
    try:
        from pipeline.data_collector import DataCollectorV5

        dc = DataCollectorV5()
        print("  DataCollectorV5 imported OK")
        results.append(("data_collector_import", True, "OK"))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("data_collector_import", False, str(e)))

    # 2. Test section writer
    print("\n[2] Section Writer")
    try:
        from pipeline.section_writer import SectionWriter

        sw = SectionWriter()

        # Check exemplar injection
        if hasattr(sw, "_build_exemplar_injection"):
            print("  Exemplar injection: OK")
            results.append(("exemplar_injection", True, "OK"))
        else:
            print("  Exemplar injection: MISSING")
            results.append(("exemplar_injection", False, "Missing"))

        # Check prompt builder
        if hasattr(sw, "_build_prompt_v4"):
            print("  Prompt builder v4: OK")
            results.append(("prompt_builder", True, "OK"))
        else:
            print("  Prompt builder v4: MISSING")
            results.append(("prompt_builder", False, "Missing"))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("section_writer", False, str(e)))

    # 3. Test IronGate
    print("\n[3] IronGate")
    try:
        from pipeline.iron_gate import IronGate

        # Create temp report
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test Report\n\nTest content.")
            temp_path = f.name

        gate = IronGate(report_path=temp_path)

        if hasattr(gate, "_run_irongate_v2_checks"):
            print("  V2 verification: OK")
            results.append(("irongate_v2", True, "OK"))
        else:
            print("  V2 verification: MISSING")
            results.append(("irongate_v2", False, "Missing"))

        import os

        os.unlink(temp_path)
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("irongate", False, str(e)))

    # 4. Test Exemplar Bank
    print("\n[4] Exemplar Bank")
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from exemplar_retriever import ExemplarRetriever

        retriever = ExemplarRetriever()
        exemplars = retriever.retrieve(section="利润表分析", n=2)

        if exemplars:
            print("  Retriever: OK (%d exemplars)" % len(exemplars))
            results.append(("exemplar_retriever", True, "%d exemplars" % len(exemplars)))
        else:
            print("  Retriever: NO EXEMPLARS")
            results.append(("exemplar_retriever", False, "No exemplars"))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("exemplar_bank", False, str(e)))

    # 5. Test Exemplar Sanitizer
    print("\n[5] Exemplar Sanitizer")
    try:
        from exemplar_injector import ExemplarSanitizer

        dirty = "AI generated content with [E1] placeholders."
        clean = ExemplarSanitizer.sanitize(dirty, max_length=50)

        if "AI" not in clean and len(clean) <= 50:
            print("  Sanitizer: OK")
            results.append(("sanitizer", True, "OK"))
        else:
            print("  Sanitizer: FAIL")
            results.append(("sanitizer", False, "Output: %s" % clean))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("sanitizer", False, str(e)))

    # 6. Test Golden Numeric Verifier
    print("\n[6] Golden Numeric Verifier")
    try:
        from golden_numeric_verify import GoldenNumericVerifier

        verifier = GoldenNumericVerifier()
        print("  Verifier: OK (%d truth entries)" % len(verifier.truth_set))
        results.append(("verifier", True, "%d entries" % len(verifier.truth_set)))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("verifier", False, str(e)))

    # 7. Test Track Record
    print("\n[7] Track Record")
    try:
        from core.tools.track_record import TrackRecordManager

        manager = TrackRecordManager()
        print("  TrackRecordManager: OK (%d predictions)" % manager.record.total)
        results.append(("track_record", True, "%d predictions" % manager.record.total))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("track_record", False, str(e)))

    # 8. Test IronGate V2 Standalone
    print("\n[8] IronGate V2 Standalone")
    try:
        from irongate_v2 import IronGateV2

        gate_v2 = IronGateV2()
        result = gate_v2.verify("Test report content for verification.")

        if hasattr(result, "overall_score"):
            print("  V2 Standalone: OK (score=%.2f)" % result.overall_score)
            results.append(("irongate_v2_standalone", True, "score=%.2f" % result.overall_score))
        else:
            print("  V2 Standalone: FAIL")
            results.append(("irongate_v2_standalone", False, "No score attribute"))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("irongate_v2_standalone", False, str(e)))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    total = len(results)

    print("Total: %d" % total)
    print("Passed: %d" % passed)
    print("Failed: %d" % failed)
    print("Pass Rate: %.2f%%" % (passed / total * 100 if total > 0 else 0))

    if failed > 0:
        print("\nFailed Tests:")
        for name, p, msg in results:
            if not p:
                print("  [%s] %s" % (name, msg))

    print("=" * 60)

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total if total > 0 else 0,
        "results": [{"name": n, "passed": p, "message": m} for n, p, m in results],
    }


def main():
    summary = test_full_pipeline()

    # Save results
    output = ROOT / "benchmark" / "e2e_smoke_results.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nResults saved: %s" % output)

    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
