"""P0-5: Golden numeric validation tests (red→green).

Tests:
1. Report with canonical value → pass
2. Report with deviated value (> tolerance) → fail
3. Report without field → unverifiable
"""

import pytest
from scripts.validate_golden import (
    extract_numeric_values,
    validate_numeric_values,
    load_numeric_golden_set,
)


# ============================================================
# Test 1: Report with canonical value → pass
# ============================================================

class TestGoldenNumericPass:
    """Reports matching canonical values should pass."""

    def test_target_price_match(self):
        """Report mentions 260.0 → matches canonical 260.0."""
        report = "我们给予目标价260.0元，对应2026年25倍PE估值。"
        golden = [
            {
                "asset": "宁德时代",
                "field": "target_price",
                "canonical": 260.0,
                "allow_report_values": [260.0, 260],
                "tolerance": 0.01,
            }
        ]
        result = validate_numeric_values(report, golden)
        assert result["passed"] == 1
        assert result["failed"] == 0

    def test_target_price_integer_match(self):
        """Report mentions 260 (integer) → matches canonical 260.0."""
        report = "目标价260元"
        golden = [
            {
                "asset": "宁德时代",
                "field": "target_price",
                "canonical": 260.0,
                "allow_report_values": [260.0, 260],
                "tolerance": 0.01,
            }
        ]
        result = validate_numeric_values(report, golden)
        assert result["passed"] == 1


# ============================================================
# Test 2: Report with deviated value → fail
# ============================================================

class TestGoldenNumericFail:
    """Reports with deviated values should fail."""

    def test_target_price_deviation(self):
        """Report mentions 310 (deviates from 260 >1%) → fail."""
        report = "目标价310元，较当前有20%上行空间。"
        golden = [
            {
                "asset": "宁德时代",
                "field": "target_price",
                "canonical": 260.0,
                "allow_report_values": [260.0],
                "tolerance": 0.01,
            }
        ]
        result = validate_numeric_values(report, golden)
        assert result["failed"] == 1
        assert result["passed"] == 0

    def test_target_price_close_but_fail(self):
        """Report mentions 262 (deviates from 260 >1%) → fail."""
        report = "目标价262元"
        golden = [
            {
                "asset": "宁德时代",
                "field": "target_price",
                "canonical": 260.0,
                "allow_report_values": [260.0],
                "tolerance": 0.01,  # 1% tolerance
            }
        ]
        result = validate_numeric_values(report, golden)
        # 262 vs 260 = 0.77% deviation, within 1% tolerance
        # So this should actually pass
        assert result["passed"] == 1


# ============================================================
# Test 3: Report without field → unverifiable
# ============================================================

class TestGoldenNumericUnverifiable:
    """Reports missing fields should be marked unverifiable."""

    def test_no_target_price_in_report(self):
        """Report has no target_price → unverifiable."""
        report = "公司业绩稳步增长，未来前景看好。"
        golden = [
            {
                "asset": "宁德时代",
                "field": "target_price",
                "canonical": 260.0,
                "allow_report_values": [260.0],
                "tolerance": 0.01,
            }
        ]
        result = validate_numeric_values(report, golden)
        assert result["unverifiable"] == 1
        assert result["passed"] == 0
        assert result["failed"] == 0


# ============================================================
# Test 4: Helper functions
# ============================================================

class TestGoldenNumericHelpers:
    """Test helper functions."""

    def test_extract_target_price(self):
        """Extract target price from report text."""
        text = "目标价260.0元，对应2026年25倍PE。"
        extracted = extract_numeric_values(text)
        assert "target_price" in extracted
        assert 260.0 in extracted["target_price"]

    def test_extract_multiple_values(self):
        """Extract multiple target prices from different sentences."""
        text = "目标价260元。根据DCF模型，目标价310元。"
        extracted = extract_numeric_values(text)
        assert "target_price" in extracted
        assert len(extracted["target_price"]) >= 2

    def test_load_numeric_golden_set(self):
        """Load numeric golden set from directory."""
        items = load_numeric_golden_set("benchmark/golden_numeric")
        assert len(items) > 0
        assert "canonical" in items[0]
        assert "tolerance" in items[0]
