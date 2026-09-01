"""S6-1/S6-2/S6-3/S6-4: Compliance tests."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def test_rating_tracker_import():
    from scripts.rating_tracker import main

    assert callable(main)


def test_target_price_reminder_import():
    from scripts.target_price_reminder import main

    assert callable(main)


def test_compliance_clauses_import():
    from core.compliance_clauses import get_clause

    assert callable(get_clause)


def test_compliance_clauses_all_types():
    from core.compliance_clauses import get_clause

    for rt in ["listed_company", "industry_deep", "unlisted_company", "decision_memo"]:
        clause = get_clause(rt)
        assert isinstance(clause, str)
        assert len(clause) > 10


def test_sensitive_info_scan_import():
    from scripts.sensitive_info_scan import scan_text

    assert callable(scan_text)


def test_sensitive_info_scan_detects():
    from scripts.sensitive_info_scan import scan_text

    findings = scan_text("本报告基于未披露的内部数据和未公开财报", "test.md")
    assert len(findings) > 0
    categories = {f["category"] for f in findings}
    assert "unreleased_financials" in categories or "unannounced_ma" in categories


def test_sensitive_info_scan_clean():
    from scripts.sensitive_info_scan import scan_text

    findings = scan_text("本报告基于公开数据和公司公告", "test.md")
    high = [f for f in findings if f["severity"] == "high"]
    assert len(high) == 0
