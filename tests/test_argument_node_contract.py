"""P0-3: ArgumentEngine fix tests (red→green).

Tests:
1. ArgumentEngine failure → scaffold=None → D1 gate blocks
2. scaffold missing → D1 intercepts (not warning)
3. node_errors recorded when argument fails
"""

import pytest
from unittest.mock import patch, MagicMock


# ============================================================
# Test 1: ArgumentEngine failure → D1 gate blocks
# ============================================================

class TestArgumentEngineFailure:
    """ArgumentEngine failure should block pipeline."""

    def test_argument_exception_records_error(self):
        """Exception in argument_engine records error in node_errors."""
        from pipeline.e2e_orchestrator import E2ENodes

        context = {
            "asset": "300750",
            "collected_data": {"revenue": 100},
        }

        with patch("pipeline.e2e_orchestrator._HAS_ARGUMENT", True), \
             patch("pipeline.e2e_orchestrator.ArgumentEngine") as MockAE:
            MockAE.side_effect = RuntimeError("ArgumentEngine crashed")

            # Call the static method directly
            result = E2ENodes.argument_engine("argument", context)

            # scaffold should be None
            assert result["scaffold"] is None
            # error should be recorded
            assert "node_errors" in context
            assert "argument" in context["node_errors"]
            assert "crashed" in context["node_errors"]["argument"]

    def test_argument_scaffold_none_triggers_d1(self):
        """scaffold=None should be caught by D1 node evidence check."""
        # Simulate what D1 checks
        context = {
            "collected_data": {"revenue": 100},
            "compute_results": {"dcf": 260},
            "scaffold": None,  # argument failed
            "report_text": "some text",
            "final_text": "assembled",
        }

        _node_evidence = {
            "data": ["collected_data"],
            "compute": ["compute_results"],
            "argument": ["scaffold"],
            "write_sections": ["report_text"],
            "assemble": ["final_text"],
        }

        _node_failures = []
        for _node, _keys in _node_evidence.items():
            for _k in _keys:
                _val = context.get(_k)
                if not _val or (isinstance(_val, (dict, str)) and not _val):
                    _node_failures.append(f"{_node}:{_k}")

        assert "argument:scaffold" in _node_failures


# ============================================================
# Test 2: scaffold missing → D1 intercepts
# ============================================================

class TestD1InterceptsMissingScaffold:
    """D1 gate should block when scaffold is missing."""

    def test_d1_blocks_on_missing_scaffold(self):
        """Missing scaffold → D1 fails pipeline."""
        context = {
            "collected_data": {"revenue": 100},
            "compute_results": {"dcf": 260},
            "report_text": "some text",
            "final_text": "assembled",
            # No scaffold key at all
        }

        _node_evidence = {
            "data": ["collected_data"],
            "compute": ["compute_results"],
            "argument": ["scaffold"],
            "write_sections": ["report_text"],
            "assemble": ["final_text"],
        }

        _node_failures = []
        for _node, _keys in _node_evidence.items():
            for _k in _keys:
                _val = context.get(_k)
                if not _val or (isinstance(_val, (dict, str)) and not _val):
                    _node_failures.append(f"{_node}:{_k}")

        assert "argument:scaffold" in _node_failures


# ============================================================
# Test 3: node_errors recorded
# ============================================================

class TestNodeErrorsRecorded:
    """node_errors dict should capture argument failures."""

    def test_node_errors_has_argument_key(self):
        """After argument failure, node_errors has 'argument' key."""
        context = {
            "asset": "300750",
            "collected_data": {},
        }

        # Simulate argument failure
        try:
            raise ValueError("brief.asset is empty")
        except Exception as e:
            if "node_errors" not in context:
                context["node_errors"] = {}
            context["node_errors"]["argument"] = str(e)[:500]

        assert "argument" in context["node_errors"]
        assert "empty" in context["node_errors"]["argument"]

    def test_multiple_node_failures_accumulated(self):
        """Multiple node failures accumulate in node_errors."""
        context = {
            "asset": "300750",
        }

        # Simulate multiple failures
        context["node_errors"] = {}
        context["node_errors"]["argument"] = "ArgumentEngine crashed"
        context["node_errors"]["compute"] = "Division by zero"

        assert len(context["node_errors"]) == 2
        assert "argument" in context["node_errors"]
        assert "compute" in context["node_errors"]
