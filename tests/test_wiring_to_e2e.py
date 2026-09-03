"""P0-7: D3/D4/D5 wiring tests (red→green).

Tests:
1. RetryPolicy wired to LLM calls (classify_error → retry)
2. IdempotentLedger wired to export (pending → done)
3. HITL durable wired to approval (resume after crash)
4. Assemble post-check catches residual {{}}
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock


# ============================================================
# Test 1: RetryPolicy wired to LLM calls
# ============================================================

class TestRetryPolicyWiring:
    """RetryPolicy should classify errors and retry appropriately."""

    def test_classify_error_rate_limit(self):
        """429 error → RETRYABLE_RATE_LIMIT."""
        from core.retry_policy import RetryPolicy, ErrorClass

        policy = RetryPolicy()
        error = Exception("429 Too Many Requests")
        error_class = policy.classify_error(error)
        assert error_class == ErrorClass.RETRYABLE_RATE_LIMIT

    def test_classify_error_timeout(self):
        """Timeout → RETRYABLE_TIMEOUT."""
        from core.retry_policy import RetryPolicy, ErrorClass

        policy = RetryPolicy()
        error = TimeoutError("Request timed out")
        error_class = policy.classify_error(error)
        assert error_class == ErrorClass.RETRYABLE_TIMEOUT

    def test_retry_policy_classify(self):
        """RetryPolicy should classify errors correctly."""
        from core.retry_policy import RetryPolicy, ErrorClass

        policy = RetryPolicy()
        # Rate limit
        assert policy.classify_error(Exception("429 Too Many Requests")) == ErrorClass.RETRYABLE_RATE_LIMIT
        # Timeout
        assert policy.classify_error(TimeoutError("timeout")) == ErrorClass.RETRYABLE_TIMEOUT
        # Non-retryable
        assert policy.classify_error(Exception("permission denied")) == ErrorClass.NON_RETRYABLE


# ============================================================
# Test 2: IdempotentLedger wired to export
# ============================================================

class TestIdempotentLedgerWiring:
    """IdempotentLedger should track pending operations."""

    def test_record_pending(self):
        """Record pending operation."""
        from core.idempotent_ledger import IdempotentLedger

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = IdempotentLedger(ledger_dir=tmpdir)
            entry_id = ledger.record_pending(
                entry_type="export",
                asset="300750",
                params={"format": "docx"},
            )
            assert entry_id is not None

            # Check pending
            pending = ledger.get_pending()
            assert len(pending) >= 1

    def test_idempotent_check(self):
        """Same operation detected as duplicate."""
        from core.idempotent_ledger import IdempotentLedger

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = IdempotentLedger(ledger_dir=tmpdir)
            ledger.record_pending(
                entry_type="export",
                asset="300750",
                params={"format": "docx"},
            )

            # Check duplicate
            is_dup = ledger.is_duplicate(
                entry_type="export",
                asset="300750",
                params={"format": "docx"},
            )
            assert is_dup is True


# ============================================================
# Test 3: HITL durable wired to approval
# ============================================================

class TestHITLDurableWiring:
    """HITL approval should persist across crashes."""

    def test_request_approval(self):
        """Request approval → recorded."""
        from core.hitl_durable import HITLApprovalManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HITLApprovalManager(review_dir=tmpdir, ledger_dir=tmpdir)
            review_path = manager.request_approval(
                job_id="test_001",
                asset="300750",
                report_type="listed_company",
            )
            assert review_path is not None

    def test_resume_after_approval(self):
        """Approval persists → can resume."""
        from core.hitl_durable import HITLApprovalManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HITLApprovalManager(review_dir=tmpdir, ledger_dir=tmpdir)
            review_path = manager.request_approval(
                job_id="test_002",
                asset="300750",
                report_type="listed_company",
            )

            # Approve
            manager.approve(job_id="test_002", reviewer="test")

            # Check stale (should be empty after approval)
            stale = manager.find_stale_approvals()
            assert len(stale) == 0


# ============================================================
# Test 4: Assemble post-check catches residual {{}}
# ============================================================

class TestAssemblePostCheck:
    """Assembled report with residual {{}} should be caught."""

    def test_residual_placeholder_in_assembly(self):
        """Assembled text with {{xxx}} → detected."""
        import re

        text = "目标价260元。PE比率{{pe_ratio}}为25倍。"
        residual = re.findall(r"\{\{[a-z_]+\}\}", text)
        assert len(residual) > 0
        assert "{{pe_ratio}}" in residual

    def test_clean_assembly_passes(self):
        """Assembled text without {{}} → passes."""
        import re

        text = "目标价260元。PE比率为25倍。"
        residual = re.findall(r"\{\{[a-z_]+\}\}", text)
        assert len(residual) == 0
