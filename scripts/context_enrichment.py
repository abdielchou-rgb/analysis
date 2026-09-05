#!/usr/bin/env python
"""
Context Enrichment Module for SAC Data Pipeline.

Enhances data collection by:
1. Retrieving sector-aligned historical research reports
2. Enriching with AlphaFin research/news data
3. Providing structured financial data from FinRpt
4. Building context windows for section_writer

Usage:
    from scripts.context_enrichment import ContextEnricher
    enricher = ContextEnricher()
    context = enricher.enrich(
        stock_code="600036.SS",
        section="利润表分析",
        raw_data={...}
    )
"""

import json
from pathlib import Path

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
EXEMPLAR_BANK = ROOT / "benchmark" / "exemplar_bank"
ALPHAFIN = ROOT / "benchmark" / "external_datasets" / "AlphaFin"
FINRPT = ROOT / "benchmark" / "external_datasets" / "FinRpt"


class ContextEnricher:
    """Enrich data collection with historical context."""

    def __init__(self):
        self.exemplar_index = []
        self.alphafin_research = []
        self.alphafin_news = []
        self._load_data()

    def _load_data(self):
        """Load all reference data."""
        # Load exemplar index
        exemplar_path = EXEMPLAR_BANK / "exemplar_index.jsonl"
        if exemplar_path.exists():
            with open(exemplar_path, encoding="utf-8") as f:
                for line in f:
                    self.exemplar_index.append(json.loads(line))

        # Load AlphaFin research
        research_path = ALPHAFIN / "train" / "research.json"
        if research_path.exists():
            with open(research_path, encoding="utf-8") as f:
                self.alphafin_research = json.load(f)

        # Load AlphaFin news
        news_path = ALPHAFIN / "train" / "fin_news.json"
        if news_path.exists():
            with open(news_path, encoding="utf-8") as f:
                self.alphafin_news = json.load(f)

    def enrich(
        self,
        stock_code: str,
        section: str,
        raw_data: dict,
        max_context_tokens: int = 4000,
    ) -> dict:
        """Enrich raw data with historical context.

        Args:
            stock_code: Target company stock code
            section: SAC section name
            raw_data: Raw collected data
            max_context_tokens: Maximum context window size

        Returns:
            Enriched context dict with historical references
        """
        context = {
            "target_stock": stock_code,
            "section": section,
            "raw_data": raw_data,
            "historical_reports": [],
            "related_research": [],
            "related_news": [],
            "financial_benchmarks": {},
        }

        # 1. Retrieve historical reports for same sector
        context["historical_reports"] = self._get_historical_reports(stock_code, section, limit=5)

        # 2. Retrieve related research from AlphaFin
        context["related_research"] = self._get_related_research(stock_code, limit=3)

        # 3. Retrieve related news
        context["related_news"] = self._get_related_news(stock_code, limit=5)

        # 4. Add financial benchmarks
        context["financial_benchmarks"] = self._get_financial_benchmarks(stock_code)

        return context

    def _get_historical_reports(self, stock_code: str, section: str, limit: int = 5) -> list:
        """Get historical reports for the same sector."""
        # Find reports with similar stock code prefix (same sector heuristic)
        prefix = stock_code.split(".")[0][:3]

        candidates = []
        for ex in self.exemplar_index:
            ex_prefix = ex["stock_code"].split(".")[0][:3]
            if section in ex.get("sections", {}):
                candidates.append(
                    {
                        "stock_code": ex["stock_code"],
                        "date": ex["date"],
                        "section_data": ex["sections"][section],
                    }
                )

        # Sort by date (most recent first)
        candidates.sort(key=lambda x: x["date"], reverse=True)
        return candidates[:limit]

    def _get_related_research(self, stock_code: str, limit: int = 3) -> list:
        """Get related research from AlphaFin."""
        # Simple keyword matching (production should use embedding search)
        related = []
        for rec in self.alphafin_research[:1000]:  # Sample for speed
            instruction = rec.get("instruction", "").lower()
            output = rec.get("output", "").lower()

            # Check for relevance
            if any(
                kw in instruction or kw in output
                for kw in [
                    stock_code.split(".")[0],
                    "研报",
                    "分析",
                    "投资",
                ]
            ):
                related.append(
                    {
                        "instruction": rec["instruction"][:200],
                        "output": rec["output"][:200],
                    }
                )
                if len(related) >= limit:
                    break

        return related

    def _get_related_news(self, stock_code: str, limit: int = 5) -> list:
        """Get related news from AlphaFin."""
        related = []
        for rec in self.alphafin_news[:1000]:  # Sample for speed
            instruction = rec.get("instruction", "").lower()
            output = rec.get("output", "").lower()

            if any(
                kw in instruction or kw in output
                for kw in [
                    stock_code.split(".")[0],
                    "新闻",
                    "公告",
                    "事件",
                ]
            ):
                related.append(
                    {
                        "instruction": rec["instruction"][:200],
                        "output": rec["output"][:200],
                    }
                )
                if len(related) >= limit:
                    break

        return related

    def _get_financial_benchmarks(self, stock_code: str) -> dict:
        """Get financial benchmarks from FinRpt."""
        # Find matching record
        for ex in self.exemplar_index:
            if ex["stock_code"] == stock_code:
                return {
                    "income_data": ex["sections"].get("income", {}).get("input_data", ""),
                    "balance_data": ex["sections"].get("balance", {}).get("input_data", ""),
                    "cash_data": ex["sections"].get("cash", {}).get("input_data", ""),
                }
        return {}

    def format_context_for_prompt(self, context: dict) -> str:
        """Format enriched context for prompt injection."""
        lines = []

        # Historical reports
        if context["historical_reports"]:
            lines.append("## 历史研报参考")
            for i, report in enumerate(context["historical_reports"][:3]):
                lines.append(f"\n### 参考 {i + 1}（{report['stock_code']}，{report['date']}）")
                section_data = report.get("section_data", {})
                output = section_data.get("output_raw", "")
                if output:
                    lines.append(output[:500])
            lines.append("")

        # Related research
        if context["related_research"]:
            lines.append("## 相关研究")
            for i, research in enumerate(context["related_research"][:2]):
                lines.append(f"\n### 研究 {i + 1}")
                lines.append(f"问题：{research['instruction'][:100]}")
                lines.append(f"分析：{research['output'][:200]}")
            lines.append("")

        # Related news
        if context["related_news"]:
            lines.append("## 相关新闻")
            for i, news in enumerate(context["related_news"][:3]):
                lines.append(f"\n### 新闻 {i + 1}")
                lines.append(f"内容：{news['instruction'][:100]}")
                lines.append(f"影响：{news['output'][:150]}")
            lines.append("")

        return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Context enrichment for SAC pipeline")
    parser.add_argument("--stock", required=True, help="Stock code")
    parser.add_argument("--section", required=True, help="Section name")
    parser.add_argument("--data", help="Path to raw data JSON")
    args = parser.parse_args()

    enricher = ContextEnricher()

    raw_data = {}
    if args.data:
        raw_data = json.loads(Path(args.data).read_text(encoding="utf-8"))

    context = enricher.enrich(
        stock_code=args.stock,
        section=args.section,
        raw_data=raw_data,
    )

    # Print formatted context
    print(enricher.format_context_for_prompt(context))


if __name__ == "__main__":
    main()
