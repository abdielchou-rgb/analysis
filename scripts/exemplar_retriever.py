#!/usr/bin/env python
"""
Diversity-aware exemplar retrieval for SAC section_writer.

Selects exemplars that maximize coverage of:
- Different sectors/industries
- Different task types (income, balance, cash, etc.)
- Different quality levels (top-tier + mid-tier for robustness)
- Different stock characteristics (large-cap vs small-cap, profit vs loss)

Usage:
    from scripts.exemplar_retriever import ExemplarRetriever
    r = ExemplarRetriever()
    exemplars = r.retrieve(section="利润表分析", n=3, sector="银行")
"""

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Optional

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
INDEX = ROOT / "benchmark" / "exemplar_bank" / "exemplar_index.jsonl"

# Section name → task key mapping (reverse of TASK_MAP in build_exemplar_bank.py)
SECTION_TO_TASK = {
    "利润表分析": "income",
    "资产负债表分析": "balance",
    "现金流量表分析": "cash",
    "财务综述": "finance_write",
    "投资建议报告": "report_write",
    "趋势分析": "trend_write",
    "风险提示": "risk",
    "新闻综述": "news_write",
    "新闻分析": "news_anlyzer",
}


class ExemplarRetriever:
    """Diversity-aware exemplar retrieval for SAC pipeline."""

    def __init__(self):
        self.exemplars = []
        self.by_section = defaultdict(list)  # section_name → [exemplars]
        self.by_sector = defaultdict(list)
        self._load()

    def _load(self):
        with open(INDEX, encoding="utf-8") as f:
            for line in f:
                ex = json.loads(line)
                self.exemplars.append(ex)
                # Index by section name (not task key)
                for task_key, section_data in ex["sections"].items():
                    section_name = section_data.get("section_name", task_key)
                    self.by_section[section_name].append(ex)
                self.by_sector[ex["sector"]].append(ex)

    def retrieve(
        self,
        section: str,
        n: int = 3,
        sector: Optional[str] = None,
        exclude_stocks: Optional[set] = None,
        quality_tier: str = "top",  # "top", "mixed", "random"
    ) -> list[dict]:
        """Retrieve n diverse exemplars for a given section.

        Args:
            section: SAC section name (e.g., "利润表分析", "风险提示")
            n: Number of exemplars to retrieve
            sector: Optional sector filter
            exclude_stocks: Stock codes to exclude (e.g., current target company)
            quality_tier: "top" = best quality only, "mixed" = top + mid, "random" = random

        Returns:
            List of exemplar dicts with section-specific data
        """
        candidates = self.by_section.get(section, [])
        if not candidates:
            return []

        # Filter by sector if specified
        if sector:
            sector_filtered = [ex for ex in candidates if ex["sector"] == sector]
            if len(sector_filtered) >= n * 2:
                candidates = sector_filtered

        # Exclude specific stocks
        if exclude_stocks:
            candidates = [ex for ex in candidates if ex["stock_code"] not in exclude_stocks]

        if not candidates:
            return []

        # Sort by quality
        candidates.sort(key=lambda x: x["sections"].get(section, {}).get("output_length", 0), reverse=True)

        # Diversity-aware selection
        if quality_tier == "top":
            # Take from top 20%
            pool_size = max(n * 3, len(candidates) // 5)
            pool = candidates[:pool_size]
        elif quality_tier == "mixed":
            # 50% top, 50% mid
            top_pool = candidates[: len(candidates) // 3]
            mid_pool = candidates[len(candidates) // 3 : 2 * len(candidates) // 3]
            pool = top_pool + mid_pool
        else:
            pool = candidates

        # Greedy diversity selection: maximize sector diversity
        selected = []
        seen_sectors = set()
        seen_stocks = set()

        # First pass: one per sector
        for ex in pool:
            if len(selected) >= n:
                break
            sector_id = ex["sector"]
            stock = ex["stock_code"]
            if sector_id not in seen_sectors and stock not in seen_stocks:
                selected.append(ex)
                seen_sectors.add(sector_id)
                seen_stocks.add(stock)

        # Second fill remaining slots
        for ex in pool:
            if len(selected) >= n:
                break
            stock = ex["stock_code"]
            if stock not in seen_stocks:
                selected.append(ex)
                seen_stocks.add(stock)

        # Pad with random if needed
        if len(selected) < n:
            remaining = [ex for ex in pool if ex not in selected]
            random.shuffle(remaining)
            selected.extend(remaining[: n - len(selected)])

        # Format output - look up by task key
        task_key = SECTION_TO_TASK.get(section, section)
        result = []
        for ex in selected[:n]:
            section_data = ex["sections"].get(task_key, {})
            result.append(
                {
                    "id": ex["id"],
                    "stock_code": ex["stock_code"],
                    "sector": ex["sector"],
                    "quality_score": ex["quality_score"],
                    "section_name": section_data.get("section_name", section),
                    "input_data": section_data.get("input_data", ""),
                    "output_raw": section_data.get("output_raw", ""),
                    "output_parsed": section_data.get("output_parsed"),
                }
            )

        return result

    def get_stats(self) -> dict:
        """Return retrieval statistics."""
        return {
            "total_exemplars": len(self.exemplars),
            "sections": {s: len(exs) for s, exs in self.by_section.items()},
            "sectors": {s: len(exs) for s, exs in self.by_sector.items()},
        }


# ── CLI interface ─────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Exemplar retrieval for SAC pipeline")
    parser.add_argument("--section", required=True, help="Section name (e.g., 利润表分析)")
    parser.add_argument("--n", type=int, default=3, help="Number of exemplars")
    parser.add_argument("--sector", help="Optional sector filter")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    args = parser.parse_args()

    r = ExemplarRetriever()

    if args.stats:
        stats = r.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    exemplars = r.retrieve(section=args.section, n=args.n, sector=args.sector)
    for i, ex in enumerate(exemplars):
        print(f"\n{'=' * 60}")
        print(f"Exemplar {i + 1}: {ex['stock_code']} (sector={ex['sector']}, quality={ex['quality_score']})")
        print(f"Section: {ex['section_name']}")
        print(f"Output ({len(ex['output_raw'])} chars):")
        print(ex["output_raw"][:500])


if __name__ == "__main__":
    main()
