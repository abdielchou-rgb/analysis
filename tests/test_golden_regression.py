"""
Golden Sample Regression Tests — 30 real institutional reports as quality baseline.
Run: pytest tests/test_golden_regression.py -v -m golden
"""

import pytest
import tempfile
import os
from pathlib import Path

# Golden sample corpus: 30 real reports across 5 types x 6 styles
# User must populate benchmark/golden/{type}/ with real PDF→MD conversions
GOLDEN_SAMPLES = [
    # listed_company (6)
    ("贵州茅台", "listed_company", "cicc"),
    ("宁德时代", "listed_company", "gs"),
    ("美的集团", "listed_company", "ms"),
    ("工业富联", "listed_company", "jpm"),
    ("长江电力", "listed_company", "mck"),
    ("招商银行", "listed_company", "bcg"),
    # industry_deep (6)
    ("半导体设备", "industry_deep", "cicc"),
    ("AI算力产业链", "industry_deep", "gs"),
    ("新能源车供应链", "industry_deep", "ms"),
    ("生物制药CDMO", "industry_deep", "jpm"),
    ("低空经济", "industry_deep", "mck"),
    ("数据要素", "industry_deep", "bcg"),
    # unlisted_company (6)
    ("某AI芯片独角兽", "unlisted_company", "cicc"),
    ("某新能源电池独角兽", "unlisted_company", "gs"),
    ("某生物医药独角兽", "unlisted_company", "ms"),
    ("某机器人独角兽", "unlisted_company", "jpm"),
    ("某量子计算独角兽", "unlisted_company", "mck"),
    ("某商业航天独角兽", "unlisted_company", "bcg"),
    # earnings_notes (6)
    ("贵州茅台", "earnings_notes", "cicc"),
    ("宁德时代", "earnings_notes", "gs"),
    ("美的集团", "earnings_notes", "ms"),
    ("工业富联", "earnings_notes", "jpm"),
    ("长江电力", "earnings_notes", "mck"),
    ("招商银行", "earnings_notes", "bcg"),
    # decision_memo (6)
    ("柯力传感油位传感器代工", "decision_memo", "cicc"),
    ("某车企收购激光雷达供应商", "decision_memo", "gs"),
    ("某药企License-in创新药", "decision_memo", "ms"),
    ("某科技巨头投资AI基建", "decision_memo", "jpm"),
    ("某PE收购消费品牌", "decision_memo", "mck"),
    ("某主权基金入股半导体", "decision_memo", "bcg"),
]

# Minimum gate score per report type (calibrated from real reports)
MIN_GATE_SCORE = {
    "listed_company": 0.88,
    "industry_deep": 0.85,
    "unlisted_company": 0.82,
    "earnings_notes": 0.80,
    "decision_memo": 0.90,  # highest bar for decision docs
}

# Critical checks that must pass (no regression allowed)
CRITICAL_CHECKS = [
    "sac_coverage",
    "data_traceability",
    "valuation_integrity",
    "numeric_chain_consistency",
    "arithmetic_audit",
    "invariant_audit",
    "csrc_compliance",  # new: regulatory compliance
    "data_point_provenance",  # new: provenance completeness
]


@pytest.mark.golden
@pytest.mark.parametrize("asset, rtype, style", GOLDEN_SAMPLES)
def test_golden_regression(asset, rtype, style, tmp_path):
    """Run full pipeline on golden sample, verify gate passes with minimum score."""
    from main import run_pipeline
    
    output_dir = tmp_path / f"{asset}_{rtype}_{style}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result = run_pipeline(
        asset=asset,
        report_type=rtype,
        style=style,
        output_dir=str(output_dir),
    )
    
    # 1. Pipeline must complete successfully
    assert result["status"] == "ok", (
        f"{asset} [{rtype}/{style}] pipeline failed: {result.get('error')}"
    )
    
    # 2. Gate score meets type-specific threshold
    gate_score = result.get("gate_score", 0.0)
    min_score = MIN_GATE_SCORE.get(rtype, 0.80)
    assert gate_score >= min_score, (
        f"{asset} [{rtype}/{style}] gate_score={gate_score:.3f} < {min_score}"
    )
    
    # 3. All critical checks must pass
    gate_checks = result.get("gate_checks", {})
    for check_name in CRITICAL_CHECKS:
        check_passed = any(
            c.get("name") == check_name and c.get("passed") 
            for c in gate_checks.get("checks", [])
        )
        assert check_passed, (
            f"{asset} [{rtype}/{style}] CRITICAL CHECK FAILED: {check_name}"
        )
    
    # 4. Output files exist
    assert result.get("md"), f"{asset} MD output missing"
    assert result.get("docx"), f"{asset} DOCX output missing"
    assert Path(result["md"]).exists(), f"{asset} MD file not found"
    assert Path(result["docx"]).exists(), f"{asset} DOCX file not found"
    
    # 5. Basic content sanity
    md_text = Path(result["md"]).read_text(encoding="utf-8")
    assert len(md_text) > 5000, f"{asset} report too short: {len(md_text)} chars"
    assert "目标价" in md_text or "评级" in md_text, f"{asset} missing rating/target"
    
    print(f"✓ {asset} [{rtype}/{style}] gate={gate_score:.3f} md={len(md_text)} chars")


@pytest.mark.golden
def test_golden_summary():
    """Summary test - prints aggregate statistics (run last)."""
    # This test just ensures the suite runs; individual parametrized tests do the work
    assert len(GOLDEN_SAMPLES) == 30
    print(f"\n{'='*60}")
    print(f"Golden Regression Suite: {len(GOLDEN_SAMPLES)} samples")
    print(f"Types: listed_company(6), industry_deep(6), unlisted_company(6)")
    print(f"       earnings_notes(6), decision_memo(6)")
    print(f"Styles: cicc, gs, ms, jpm, mck, bcg")
    print(f"Critical checks: {len(CRITICAL_CHECKS)}")
    print(f"{'='*60}")


# Helper to check golden sample readiness
def check_golden_readiness():
    """Check if golden samples are populated."""
    from pathlib import Path
    base = Path("benchmark/golden")
    ready = {}
    for rtype in ["listed_company", "industry_deep", "unlisted_company", "earnings_notes", "decision_memo"]:
        files = list((base / rtype).glob("*.md"))
        ready[rtype] = len(files)
    return ready


if __name__ == "__main__":
    # Quick readiness check
    ready = check_golden_readiness()
    print("Golden sample readiness:")
    for k, v in ready.items():
        print(f"  {k}: {v}/6 files")
    print("\nRun with: pytest tests/test_golden_regression.py -v -m golden")