"""P0-4: B1 placeholder hard block tests (red→green).

Tests:
1. LLM-created {{pe_ratio}} → ValueError (blocking)
2. Normal {{tp_primary}} → replaced with compute value → no error
3. No compute value → {{tp_primary}} not replaced → ValueError
"""

import pytest
from unittest.mock import MagicMock


# ============================================================
# Test 1: LLM-created unknown placeholder → ValueError
# ============================================================

class TestPlaceholderHardBlock:
    """Residual placeholders must raise ValueError, not just warn."""

    def test_unknown_placeholder_raises_error(self):
        """{{pe_ratio}} (LLM-created) → ValueError."""
        from pipeline.section_writer import SectionWriter

        writer = SectionWriter.__new__(SectionWriter)
        writer._last_data_context = {"target_price": 260.0}

        text = "目标价{{tp_primary}}元，PE比率{{pe_ratio}}为25倍"
        with pytest.raises(ValueError, match="Residual placeholders"):
            writer._replace_placeholders(text)

    def test_multiple_unknown_placeholders(self):
        """Multiple unknowns → ValueError with all listed."""
        from pipeline.section_writer import SectionWriter

        writer = SectionWriter.__new__(SectionWriter)
        writer._last_data_context = {}

        text = "目标价{{target}}，增速{{growth}}，毛利率{{margin}}"
        with pytest.raises(ValueError, match="Residual placeholders"):
            writer._replace_placeholders(text)


# ============================================================
# Test 2: Normal {{tp_primary}} → replaced successfully
# ============================================================

class TestPlaceholderReplacementSuccess:
    """Known placeholders with compute values should be replaced."""

    def test_tp_primary_replaced(self):
        """{{tp_primary}} → 260.0 (from compute)."""
        from pipeline.section_writer import SectionWriter

        writer = SectionWriter.__new__(SectionWriter)
        writer._last_data_context = {"target_price": 260.0}

        text = "我们给予目标价{{tp_primary}}元，对应2026年25倍PE。"
        result = writer._replace_placeholders(text)
        assert "260.0" in result
        assert "{{tp_primary}}" not in result
        assert "{{" not in result  # no residual

    def test_no_placeholders_passthrough(self):
        """Text without placeholders passes through unchanged."""
        from pipeline.section_writer import SectionWriter

        writer = SectionWriter.__new__(SectionWriter)
        writer._last_data_context = {"target_price": 260.0}

        text = "我们给予目标价260元，对应2026年25倍PE。"
        result = writer._replace_placeholders(text)
        assert result == text


# ============================================================
# Test 3: Missing compute value → honest-gap (2026-09-04 revision)
# ============================================================

class TestPlaceholderMissingCompute:
    """{{tp_primary}} without valid target_price → honest-gap label, not paragraph death.

    2026-09-04 修订：P0-4 原版对 target_price 缺失也抛 ValueError，
    导致估值模块全失败时整段写作死——与 R79 honest_gap 原则矛盾。
    现行为：{{tp_primary}} → "目标价待定（估值数据不可得，待补充）"。
    未知占位符（{{xxx}} 非 tp_primary）仍然 ValueError 硬拦（见 Test 1）。
    """

    def test_tp_primary_no_compute_value(self):
        """{{tp_primary}} without target_price in context → honest-gap label."""
        from pipeline.section_writer import SectionWriter

        writer = SectionWriter.__new__(SectionWriter)
        writer._last_data_context = {}  # no target_price

        text = "目标价{{tp_primary}}元"
        result = writer._replace_placeholders(text)
        assert "{{tp_primary}}" not in result  # replaced
        assert "目标价待定" in result  # honest-gap label
        assert "{{" not in result  # no residual

    def test_tp_primary_zero_value(self):
        """{{tp_primary}} with target_price=0 → honest-gap label."""
        from pipeline.section_writer import SectionWriter

        writer = SectionWriter.__new__(SectionWriter)
        writer._last_data_context = {"target_price": 0}

        text = "目标价{{tp_primary}}元"
        result = writer._replace_placeholders(text)
        assert "{{tp_primary}}" not in result
        assert "目标价待定" in result

    def test_tp_primary_negative_value(self):
        """{{tp_primary}} with target_price<0 → honest-gap label."""
        from pipeline.section_writer import SectionWriter

        writer = SectionWriter.__new__(SectionWriter)
        writer._last_data_context = {"target_price": -10}

        text = "目标价{{tp_primary}}元"
        result = writer._replace_placeholders(text)
        assert "{{tp_primary}}" not in result
        assert "目标价待定" in result
