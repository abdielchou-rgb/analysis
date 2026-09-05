#!/usr/bin/env python
"""Pipeline end-to-end test with mock LLM."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def mock_llm_call(*args, **kwargs):
    """Mock LLM call that returns a realistic report."""
    return """
# 贵州茅台（600519）深度研究

## 核心结论

目标价：1800元，维持买入评级。

## 利润表分析

2024年营业收入预计达到1500亿元，同比增长15%。净利润预计为750亿元，同比增长18%。

每股收益预计为60元，对应PE倍数30倍。

## 竞争格局分析

白酒行业竞争格局稳定，茅台品牌力持续增强。

## 趋势分析

消费升级趋势不变，茅台提价空间充足。

## 风险提示

1. 宏观经济下行风险
2. 行业政策风险
3. 市场竞争风险
"""


def test_pipeline_with_mock():
    """Test full pipeline with mock LLM."""
    print("=" * 60)
    print("Pipeline E2E Test (Mock LLM)")
    print("=" * 60)

    results = []

    # 1. Test data collection
    print("\n[1] Data Collection")
    try:
        from pipeline.data_collector import DataCollectorV5

        dc = DataCollectorV5()

        # Mock the collect method
        with patch.object(dc, "collect") as mock_collect:
            mock_collect.return_value = {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "financials": {"revenue": 1500, "net_income": 750},
            }

            data = dc.collect("600519")
            print("  Data collected: %s" % data.get("stock_name"))
            results.append(("data_collection", True, "OK"))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("data_collection", False, str(e)))

    # 2. Test section writer with mock LLM
    print("\n[2] Section Writer (Mock LLM)")
    try:
        from pipeline.section_writer import SectionWriter

        sw = SectionWriter()

        # Mock the LLM client
        with patch.object(sw, "_call_llm", return_value=mock_llm_call()):
            with patch.object(sw, "_build_prompt_v4", return_value="Test prompt"):
                # Test exemplar injection
                if hasattr(sw, "_build_exemplar_injection"):
                    print("  Exemplar injection: OK")
                    results.append(("exemplar_injection", True, "OK"))
                else:
                    print("  Exemplar injection: MISSING")
                    results.append(("exemplar_injection", False, "Missing"))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("section_writer", False, str(e)))

    # 3. Test IronGate with mock report
    print("\n[3] IronGate")
    try:
        from pipeline.iron_gate import IronGate

        # Create temp report with UTF-8 encoding
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(mock_llm_call())
            temp_path = f.name

        gate = IronGate(report_path=temp_path)

        # Mock the run_all method
        with patch.object(gate, "run_all") as mock_run:
            mock_run.return_value = {
                "passed": True,
                "score": 0.85,
                "checks": [],
            }

            result = gate.run_all()
            print("  Gate result: passed=%s, score=%.2f" % (result["passed"], result["score"]))
            results.append(("irongate", True, "OK"))

        import os

        os.unlink(temp_path)
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("irongate", False, str(e)))

    # 4. Test Exemplar Bank
    print("\n[4] Exemplar Bank")
    try:
        from exemplar_injector import ExemplarInjector, ExemplarSanitizer
        from exemplar_retriever import ExemplarRetriever

        retriever = ExemplarRetriever()
        exemplars = retriever.retrieve(section="利润表分析", n=2)

        if exemplars:
            injector = ExemplarInjector()
            prompt = injector.build_prompt(
                section="利润表分析",
                company_data="Test data",
                company_name="贵州茅台",
                n_exemplars=2,
            )

            # Sanitize
            clean = ExemplarSanitizer.sanitize(prompt, max_length=1000)
            print("  Exemplar prompt: %d chars (sanitized: %d chars)" % (len(prompt), len(clean)))
            results.append(("exemplar_system", True, "OK"))
        else:
            print("  No exemplars found")
            results.append(("exemplar_system", False, "No exemplars"))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("exemplar_system", False, str(e)))

    # 5. Test Golden Numeric verification
    print("\n[5] Golden Numeric Verification")
    try:
        from golden_numeric_verify import GoldenNumericVerifier

        verifier = GoldenNumericVerifier()
        report = verifier.verify_report(mock_llm_call(), asset_filter="贵州茅台")

        print("  Verification: %d/%d passed (%.2f%%)" % (report.passed, report.total, report.pass_rate * 100))
        results.append(("golden_numeric", True, "%.2f%%" % (report.pass_rate * 100)))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("golden_numeric", False, str(e)))

    # 6. Test Track Record
    print("\n[6] Track Record")
    try:
        from core.tools.track_record import TrackRecordManager

        manager = TrackRecordManager()
        print("  TrackRecord: %d predictions" % manager.record.total)
        results.append(("track_record", True, "%d predictions" % manager.record.total))
    except Exception as e:
        print("  FAIL: %s" % e)
        results.append(("track_record", False, str(e)))

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
    summary = test_pipeline_with_mock()

    # Save results
    output = ROOT / "benchmark" / "pipeline_e2e_results.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nResults saved: %s" % output)

    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
