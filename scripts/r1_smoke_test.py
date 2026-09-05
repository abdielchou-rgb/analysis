#!/usr/bin/env python
"""R1: Pipeline integration smoke test."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\Claude\projects\2hao-analyst")))


def test_section_writer_exemplar():
    """Test section_writer exemplar injection."""
    try:
        from pipeline.section_writer import SectionWriter

        sw = SectionWriter()

        # Check if method exists
        if hasattr(sw, "_build_exemplar_injection"):
            print("PASS: section_writer has _build_exemplar_injection")
            return True
        else:
            print("FAIL: section_writer missing _build_exemplar_injection")
            return False
    except Exception as e:
        print("FAIL: section_writer import error:", e)
        return False


def test_iron_gate_v2():
    """Test iron_gate V2 integration."""
    try:
        # Create a temporary report for testing
        import tempfile

        from pipeline.iron_gate import IronGate

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test Report\n\nTest content for V2 verification.")
            temp_path = f.name

        gate = IronGate(report_path=temp_path)

        # Check if method exists
        if hasattr(gate, "_run_irongate_v2_checks"):
            print("PASS: iron_gate has _run_irongate_v2_checks")
            # Clean up
            import os

            os.unlink(temp_path)
            return True
        else:
            print("FAIL: iron_gate missing _run_irongate_v2_checks")
            import os

            os.unlink(temp_path)
            return False
    except Exception as e:
        print("FAIL: iron_gate import error:", e)
        return False


def test_data_collector_enrichment():
    """Test data_collector context enrichment."""
    try:
        from pipeline.data_collector import DataCollectorV5

        dc = DataCollectorV5()

        # Check if method exists
        if hasattr(dc, "_enrich_with_context"):
            print("PASS: data_collector has _enrich_with_context")
            return True
        else:
            print("FAIL: data_collector missing _enrich_with_context")
            return False
    except Exception as e:
        print("FAIL: data_collector import error:", e)
        return False


def test_exemplar_sanitizer():
    """Test exemplar sanitizer."""
    try:
        from scripts.exemplar_injector import ExemplarSanitizer

        # Test sanitization
        dirty = "This is AI generated content with [E1] placeholders and 150 characters of text that should be truncated because it is too long for the prompt injection."
        clean = ExemplarSanitizer.sanitize(dirty, max_length=50)

        # Check that AI is removed and length is truncated
        if "AI" not in clean and len(clean) <= 50:
            print("PASS: ExemplarSanitizer works")
            return True
        else:
            print("FAIL: ExemplarSanitizer output:", clean)
            return False
    except Exception as e:
        print("FAIL: ExemplarSanitizer error:", e)
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("R1: Pipeline Integration Smoke Test")
    print("=" * 60)

    results = []
    results.append(test_section_writer_exemplar())
    results.append(test_iron_gate_v2())
    results.append(test_data_collector_enrichment())
    results.append(test_exemplar_sanitizer())

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print("Results: %d/%d passed" % (passed, total))

    if passed == total:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)
