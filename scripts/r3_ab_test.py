#!/usr/bin/env python
"""R3: FinRpt A/B testing framework."""

import json
import time
from pathlib import Path


class ABTestRunner:
    """Run A/B tests for exemplar injection."""

    def __init__(self):
        self.results = []
        self.output_dir = Path(r"D:\Claude\projects\2hao-analyst\benchmark\ab_tests")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_test(self, stock, section, use_exemplars):
        """Run a single A/B test."""
        start = time.time()

        # Build prompt
        prompt = "# %s - %s\n\n" % (stock["name"], section)

        if use_exemplars:
            exemplars = self._load_exemplars(section, stock.get("sector"))
            if exemplars:
                prompt += "## 参考示例\n%s\n\n" % exemplars

        result = {
            "stock": stock["name"],
            "section": section,
            "group": "treatment" if use_exemplars else "control",
            "prompt_length": len(prompt),
            "elapsed": time.time() - start,
        }
        self.results.append(result)
        return result

    def _load_exemplars(self, section, sector):
        """Load exemplars from bank."""
        try:
            import sys

            sys.path.insert(0, str(Path(r"D:\Claude\projects\2hao-analyst\scripts")))
            from exemplar_retriever import ExemplarRetriever

            retriever = ExemplarRetriever()
            exemplars = retriever.retrieve(section=section, n=2, sector=sector)

            if exemplars:
                lines = []
                for i, ex in enumerate(exemplars):
                    lines.append("### 示例 %d" % (i + 1))
                    lines.append(ex["output_raw"][:300])
                return "\n".join(lines)
        except Exception as e:
            print("Error: %s" % e)
        return ""

    def run_all(self):
        """Run all A/B tests."""
        print("=" * 60)
        print("FinRpt A/B Test")
        print("=" * 60)

        stocks = [
            {"name": "贵州茅台", "sector": "白酒"},
            {"name": "中国平安", "sector": "保险"},
        ]
        sections = ["利润表分析", "竞争格局分析"]

        for stock in stocks:
            for section in sections:
                for use_exemplars in [False, True]:
                    group = "treatment" if use_exemplars else "control"
                    print("%s / %s / %s" % (stock["name"], section, group))
                    self.run_test(stock, section, use_exemplars)

        # Save results
        output = self.output_dir / ("ab_test_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
        output.write_text(json.dumps(self.results, indent=2, ensure_ascii=False))
        print("\nResults: %s" % output)

        # Summary
        control = [r for r in self.results if r["group"] == "control"]
        treatment = [r for r in self.results if r["group"] == "treatment"]

        avg_ctrl = sum(r["prompt_length"] for r in control) / len(control) if control else 0
        avg_treat = sum(r["prompt_length"] for r in treatment) / len(treatment) if treatment else 0

        print("\nControl avg length: %.0f" % avg_ctrl)
        print("Treatment avg length: %.0f" % avg_treat)
        print("Overhead: +%.0f chars" % (avg_treat - avg_ctrl))


if __name__ == "__main__":
    runner = ABTestRunner()
    runner.run_all()
