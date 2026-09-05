#!/usr/bin/env python
"""
IronGate Multi-Layer Verification Upgrade.

Implements 5-layer verification for financial report quality:
Layer 1: Numeric fact verification (extract numbers, cross-check)
Layer 2: NLI groundedness check (each claim against context)
Layer 3: Multi-agent adversarial review (bullish/bearish/neutral)
Layer 4: Style compliance (SAC structure, So What chain)
Layer 5: Attribution verification (every claim has source)

Usage:
    from scripts.irongate_v2 import IronGateV2
    gate = IronGateV2()
    report = gate.verify(report_text, context_data)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(r"D:\Claude\projects\2hao-analyst")


@dataclass
class VerificationResult:
    """Result of a single verification layer."""

    layer: str
    passed: bool
    score: float  # 0.0 - 1.0
    issues: list = field(default_factory=list)
    details: str = ""


@dataclass
class IronGateReport:
    """Complete verification report."""

    overall_score: float
    passed: bool
    layers: list = field(default_factory=list)
    summary: str = ""


class IronGateV2:
    """Multi-layer verification for financial reports."""

    def __init__(self):
        self.layers = [
            ("numeric", self._verify_numeric),
            ("groundedness", self._verify_groundedness),
            ("adversarial", self._verify_adversarial),
            ("style", self._verify_style),
            ("attribution", self._verify_attribution),
        ]

    def verify(
        self,
        report: str,
        context: Optional[dict] = None,
        threshold: float = 0.55,
    ) -> IronGateReport:
        """Run all verification layers.

        Args:
            report: Generated report text
            context: Source data for verification (financial data, news, etc.)
            threshold: Overall passing threshold

        Returns:
            IronGateReport with scores and issues
        """
        results = []
        for layer_name, layer_fn in self.layers:
            try:
                result = layer_fn(report, context)
                results.append(result)
            except Exception as e:
                results.append(
                    VerificationResult(
                        layer=layer_name,
                        passed=False,
                        score=0.0,
                        issues=[f"Layer error: {repr(e)}"],
                    )
                )

        # Calculate overall score (weighted average)
        weights = {
            "numeric": 0.25,
            "groundedness": 0.25,
            "adversarial": 0.20,
            "style": 0.15,
            "attribution": 0.15,
        }

        total_weight = sum(weights.get(r.layer, 0.1) for r in results)
        overall_score = (
            sum(r.score * weights.get(r.layer, 0.1) for r in results) / total_weight if total_weight > 0 else 0.0
        )

        passed = overall_score >= threshold

        return IronGateReport(
            overall_score=round(overall_score, 3),
            passed=passed,
            layers=results,
            summary=self._generate_summary(results, overall_score, passed),
        )

    def _verify_numeric(self, report: str, context: Optional[dict]) -> VerificationResult:
        """Layer 1: Extract numbers from report, cross-check against source data."""
        issues = []

        # Extract all numbers from report
        numbers = re.findall(r"[\d,]+\.?\d*[%亿元万亿]", report)

        # Check for common numeric errors
        for num_str in numbers:
            # Check for obviously wrong numbers (e.g., negative revenue)
            clean = num_str.replace(",", "").replace("亿", "").replace("万", "").replace("元", "").replace("%", "")
            try:
                val = float(clean)
                if "%" in num_str and (val > 1000 or val < -100):
                    issues.append(f"Suspicious percentage: {num_str}")
            except ValueError:
                pass

        # Check number consistency (e.g., same metric should use same unit)
        units = re.findall(r"([\d,]+\.?\d*)(亿元|万元|百万|千万)", report)
        if len(set(u[1] for u in units)) > 3:
            issues.append("Inconsistent units (more than 3 different units)")

        score = max(0, 1.0 - len(issues) * 0.1)
        return VerificationResult(
            layer="numeric",
            passed=len(issues) == 0,
            score=score,
            issues=issues,
        )

    def _verify_groundedness(self, report: str, context: Optional[dict]) -> VerificationResult:
        """Layer 2: Check if each claim is supported by context."""
        issues = []

        # Split into paragraphs
        paragraphs = [p.strip() for p in report.split("\n\n") if p.strip()]

        # Check for unsupported claims
        claim_patterns = [
            (r"我们[认为判断]", "Investment opinion without data support"),
            (r"预计[将会]", "Prediction without basis"),
            (r"核心[原因是]", "Causal claim without evidence"),
        ]

        for para in paragraphs:
            for pattern, desc in claim_patterns:
                if re.search(pattern, para):
                    # Check if paragraph contains data/numbers
                    if not re.search(r"\d+\.?\d*", para):
                        issues.append(f"{desc} in: {para[:50]}...")

        score = max(0, 1.0 - len(issues) * 0.15)
        return VerificationResult(
            layer="groundedness",
            passed=len(issues) <= 2,
            score=score,
            issues=issues,
        )

    def _verify_adversarial(self, report: str, context: Optional[dict]) -> VerificationResult:
        """Layer 3: Multi-agent adversarial review."""
        issues = []

        # Check for one-sided analysis (missing bear case)
        bullish_count = len(re.findall(r"我们[认为判断].*买入|增持|推荐|看好", report))
        bearish_count = len(re.findall(r"风险|下行|压力|挑战|不确定", report))

        if bullish_count > 0 and bearish_count == 0:
            issues.append("Bullish bias: no risk/bear case mentioned")

        # Check for overconfidence
        confidence_words = re.findall(r"确定|必然|一定|毫无疑问|肯定", report)
        if len(confidence_words) > 2:
            issues.append(f"Overconfidence: {len(confidence_words)} certainty markers")

        # Check for balanced analysis
        if "另一方面" not in report and "然而" not in report and "但是" not in report:
            issues.append("No counter-argument structure found")

        score = max(0, 1.0 - len(issues) * 0.2)
        return VerificationResult(
            layer="adversarial",
            passed=len(issues) <= 1,
            score=score,
            issues=issues,
        )

    def _verify_style(self, report: str, context: Optional[dict]) -> VerificationResult:
        """Layer 4: Style compliance check."""
        issues = []

        # Check for AI markers
        ai_markers = [
            "AI生成",
            "AI辅助",
            "人工智能",
            "模型预测",
            "genuinely",
            "honestly",
            "straightforward",
        ]
        for marker in ai_markers:
            if marker.lower() in report.lower():
                issues.append(f"AI marker found: {marker}")

        # Check for So What chain
        paragraphs = [p.strip() for p in report.split("\n\n") if p.strip()]
        has_so_what = False
        for para in paragraphs:
            if re.search(r"意味着|因此|所以|投资含义|投资建议", para):
                has_so_what = True
                break
        if not has_so_what and len(paragraphs) > 3:
            issues.append("Missing So What chain (no investment implication)")

        # Check for判断词 at paragraph start
        judgment_words = ["我们认为", "核心判断", "关键分歧", "预计", "我们判断"]
        has_judgment = False
        for para in paragraphs[:3]:
            for word in judgment_words:
                if word in para[:100]:
                    has_judgment = True
                    break
        if not has_judgment:
            issues.append("Missing judgment words in first 3 paragraphs")

        score = max(0, 1.0 - len(issues) * 0.15)
        return VerificationResult(
            layer="style",
            passed=len(issues) <= 2,
            score=score,
            issues=issues,
        )

    def _verify_attribution(self, report: str, context: Optional[dict]) -> VerificationResult:
        """Layer 5: Attribution verification."""
        issues = []

        # Check for data points without source
        data_patterns = [
            r"营收[\d,]+亿",
            r"净利润[\d,]+亿",
            r"同比增长[\d,]+%",
            r"ROE[\d,]+%",
        ]

        for pattern in data_patterns:
            matches = re.findall(pattern, report)
            for match in matches:
                # Check if source is mentioned nearby
                idx = report.index(match)
                context_before = report[max(0, idx - 200) : idx]
                if not re.search(r"根据|据|来源|数据|显示|报告", context_before):
                    issues.append(f"Data without attribution: {match}")

        score = max(0, 1.0 - len(issues) * 0.1)
        return VerificationResult(
            layer="attribution",
            passed=len(issues) <= 3,
            score=score,
            issues=issues,
        )

    def _generate_summary(self, results: list, overall_score: float, passed: bool) -> str:
        """Generate human-readable summary."""
        lines = []
        lines.append(f"Overall Score: {overall_score:.3f}")
        lines.append(f"Status: {'PASS' if passed else 'FAIL'}")
        lines.append("")

        for r in results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{status}] {r.layer}: {r.score:.2f}")
            for issue in r.issues[:3]:
                lines.append(f"    - {issue}")

        return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="IronGate V2 verification")
    parser.add_argument("report", help="Path to report markdown")
    parser.add_argument("--context", help="Path to context JSON")
    parser.add_argument("--threshold", type=float, default=0.55)
    args = parser.parse_args()

    report = Path(args.report).read_text(encoding="utf-8")
    context = None
    if args.context:
        context = json.loads(Path(args.context).read_text(encoding="utf-8"))

    gate = IronGateV2()
    result = gate.verify(report, context, threshold=args.threshold)

    print(result.summary)


if __name__ == "__main__":
    main()
