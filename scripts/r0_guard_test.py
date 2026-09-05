#!/usr/bin/env python
"""R0: Guard test - mock data cannot be written to production track_record."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\Claude\projects\2hao-analyst")))


def test_mock_rejected():
    """Mock source should be rejected by production track_record."""
    from core.tools.track_record import TrackRecordManager

    manager = TrackRecordManager()

    try:
        manager.register_prediction(
            asset="TEST_MOCK",
            report_type="test",
            industry="test",
            direction="bullish",
            bold_call="This is a mock prediction that should be rejected",
            source="mock",  # Should be rejected
        )
        print("FAIL: Mock was not rejected!")
        return False
    except ValueError as e:
        if "Invalid source" in str(e) and "mock" in str(e):
            print("PASS: Mock correctly rejected")
            return True
        else:
            print("FAIL: Wrong error:", e)
            return False


def test_pipeline_accepted():
    """Pipeline source should be accepted."""
    from core.tools.track_record import TrackRecordManager

    manager = TrackRecordManager()

    try:
        pred = manager.register_prediction(
            asset="TEST_PIPELINE_001",
            report_type="test",
            industry="test",
            direction="bullish",
            bold_call="This is a pipeline test prediction",
            source="pipeline",
        )
        # Clean up test entry
        manager.record.predictions = [p for p in manager.record.predictions if p.id != pred.id]
        manager._save()
        print("PASS: Pipeline source accepted")
        return True
    except Exception as e:
        print("FAIL: Pipeline rejected:", e)
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("R0: Mock Isolation Guard Tests")
    print("=" * 60)

    r1 = test_mock_rejected()
    r2 = test_pipeline_accepted()

    print("\n" + "=" * 60)
    if r1 and r2:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)
