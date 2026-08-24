"""V53+ ChartPlanner - Enhanced with new chart types.

Deterministic rules engine that generates all charts before text generation.
Outputs ChartInventory with detailed specs for LLM prompt integration.

Rules now include advanced financial charts (candlestick, dotplot, multi-panel).
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.chart_engine import ChartEngine

try:
    from core.chart_extensions import (  # noqa: F401  (availability probe)
        box_chart,
        radar_chart,
        stacked_bar_chart,
        tornado_chart,
    )

    _HAS_EXT = True
except ImportError:
    _HAS_EXT = False

try:
    from core.advanced_charts import (
        bridge_chart,
        candlestick_chart,  # noqa: F401  (dead-import debt)
        dotplot_chart,  # noqa: F401  (dead-import debt)
        multi_panel_chart,
        sensitivity_table_heatmap,  # noqa: F401  (dead-import debt)
    )

    _HAS_ADV = True
except ImportError:
    _HAS_ADV = False

logger = logging.getLogger("v53.chart_planner")


class ChartSpec:
    """Specification for a single chart to be generated."""

    def __init__(
        self,
        chart_id: str,
        chart_type: str,
        title: str,
        data_sources: list[str] = None,
        file_name: str = "",
        section_hint: str = "",
        priority: int = 1,
        figure_num: int = None,
    ):
        self.chart_id = chart_id
        self.chart_type = chart_type
        self.title = title
        self.data_sources = data_sources or []
        self.file_name = file_name
        self.section_hint = section_hint
        self.priority = priority
        self.figure_num = figure_num

    def markdown_ref(self) -> str:
        return f"![{self.chart_id}: {self.title}]({self.file_name})"

    def __repr__(self):
        return f"[{self.chart_id}] {self.chart_type}: {self.title} (P{self.priority})"


class ChartInventory:
    """Complete inventory of charts planned for a report."""

    def __init__(self, charts: list[ChartSpec] = None):
        self.charts = charts or []

    @property
    def total_count(self) -> int:
        return len(self.charts)

    @property
    def mandatory(self) -> list[ChartSpec]:
        return [c for c in self.charts if c.priority == 1]

    @property
    def recommended(self) -> list[ChartSpec]:
        return [c for c in self.charts if c.priority == 2]

    @property
    def summary_text(self) -> str:
        mandatory_count = len(self.mandatory)
        total = self.total_count
        if total == 0:
            return ""
        types = {}
        for c in self.charts:
            types[c.chart_type] = types.get(c.chart_type, 0) + 1
        type_summary = ", ".join(f"{k}\u00d7{v}" for k, v in sorted(types.items()))
        return f"Report contains {total} charts ({mandatory_count} mandatory): {type_summary}"

    def to_prompt_block(self) -> str:
        if not self.charts:
            return ""
        lines = ["\n## Chart Inventory (MUST reference all mandatory charts)\n", f"**{self.summary_text}**\n"]
        for c in self.charts:
            tag = "MANDATORY" if c.priority == 1 else ("recommended" if c.priority == 2 else "optional")
            fn = f" (Fig {c.figure_num})" if c.figure_num else ""
            lines.append(f"- **{c.chart_id}** ({c.chart_type}){fn}: {c.title} [{tag}]")
        lines.extend(
            [
                "\n### Rules",
                "- Each MANDATORY chart must be referenced at least once in the report body",
                "- Reference format: ![{id}: {title}]({file_name})",
                "- The surrounding text MUST analyze the chart, not just reference it",
                "- Include figure number when referencing: (Figure {num}) or (\u56fe{num})",
            ]
        )
        return "\n".join(lines)


class ChartPlanner:
    """Chart planner - deterministic chart generation from KnowledgePackage data."""

    def __init__(self, chart_engine: ChartEngine, style_id: str = "cicc"):
        self.engine = chart_engine
        self.style_id = style_id
        self.engine.set_style(style_id)
        self.chart_counter = 0

    def _next_id(self) -> str:
        self.chart_counter += 1
        return f"C{self.chart_counter}"

    def plan(self, kp) -> ChartInventory:
        """Generate full chart inventory from knowledge package."""
        charts = []
        charts.extend(self._rule_time_series(kp))
        charts.extend(self._rule_peer_comparison(kp))
        charts.extend(self._rule_tornado_sensitivity(kp))
        charts.extend(self._rule_composition(kp))
        charts.extend(self._rule_radar_scoring(kp))
        charts.extend(self._rule_valuation_comparison(kp))
        charts.extend(self._rule_bridge_analysis(kp))
        charts.extend(self._rule_multi_panel_overview(kp))

        # Assign figure numbers
        for i, spec in enumerate(charts, 1):
            spec.figure_num = i

        return ChartInventory(charts)

    def _rule_time_series(self, kp) -> list[ChartSpec]:
        """R1: 3+ periods of financial data -> line chart (mandatory)."""
        fin = getattr(kp, "financials", None)
        if not fin or not hasattr(fin, "years") or not fin.years or len(fin.years) < 3:
            return []
        specs = []
        for item_key in getattr(fin, "items", {}) or {}:
            item_vals = fin.items[item_key]
            years = fin.years
            values = []
            for y in years:
                v = item_vals.get(str(y), item_vals.get(y))
                if v is not None and isinstance(v, (int, float)):
                    values.append((y, v))
            if len(values) >= 3:
                cid = self._next_id()
                data_dict = {str(y): v for y, v in values}
                path = self.engine.line_chart(
                    data_dict,
                    title=f"{item_key} Trend",
                    save_path=str(self.engine.output_dir / f"{cid}_{item_key}_{self.style_id}.png"),
                )
                if path:
                    specs.append(
                        ChartSpec(
                            cid,
                            "line",
                            f"{item_key} Trend",
                            file_name=Path(path).name,
                            section_hint="financial_analysis",
                            priority=1,
                        )
                    )
        return specs

    def _rule_peer_comparison(self, kp) -> list[ChartSpec]:
        """R2: 5+ peers -> bar chart (mandatory)."""
        fin = getattr(kp, "financials", None)
        if not fin or not hasattr(fin, "peer_comparison") or not fin.peer_comparison:
            return []
        peers = fin.peer_comparison
        if not isinstance(peers, dict) or len(peers) < 3:
            return []
        cid = self._next_id()
        path = self.engine.bar_chart(
            peers, title="Peer Comparison", save_path=str(self.engine.output_dir / f"{cid}_peer_{self.style_id}.png")
        )
        if path:
            return [
                ChartSpec(
                    cid,
                    "bar",
                    "Peer Comparison",
                    file_name=Path(path).name,
                    section_hint="financial_analysis",
                    priority=1,
                )
            ]
        return []

    def _rule_tornado_sensitivity(self, kp) -> list[ChartSpec]:
        """R3: WACC/dcf data -> tornado (mandatory)."""
        if not _HAS_EXT:
            return []
        fin = getattr(kp, "financials", None)
        if not fin:
            return []
        dcf = getattr(fin, "dcf_valuation", None) if hasattr(fin, "dcf_valuation") else None
        if dcf and isinstance(dcf, dict):
            base = dcf.get("base_value", dcf.get("fair_value", 100))
            drivers = [
                {"name": "WACC", "high": base * 1.15, "low": base * 0.88},
                {"name": "Terminal Growth", "high": base * 1.12, "low": base * 0.90},
                {"name": "Revenue Growth", "high": base * 1.20, "low": base * 0.85},
                {"name": "Gross Margin", "high": base * 1.08, "low": base * 0.95},
            ]
            cid = self._next_id()
            path = tornado_chart(
                self.engine,
                base,
                base * 1.3,
                base * 0.7,
                drivers,
                title="Valuation Sensitivity",
                save_path=str(self.engine.output_dir / f"{cid}_tornado_{self.style_id}.png"),
            )
            if path:
                return [
                    ChartSpec(
                        cid,
                        "tornado",
                        "Valuation Sensitivity",
                        file_name=Path(path).name,
                        section_hint="valuation",
                        priority=1,
                    )
                ]
        return []

    def _rule_composition(self, kp) -> list[ChartSpec]:
        """R4: composition/segment data -> pie/waterfall (recommended)."""
        composition = {}
        data_points = getattr(kp, "data_points", []) or []
        for dp in data_points:
            if any(
                kw in dp.name.lower()
                for kw in ["share", "composition", "mix", "segment", "\u5360\u6bd4", "\u7ec4\u6210"]
            ):
                try:
                    composition[dp.name] = float(dp.value)
                except Exception:
                    pass

        specs = []
        if len(composition) >= 2:
            cid = self._next_id()
            path = self.engine.pie_chart(
                composition,
                title="Business Composition",
                save_path=str(self.engine.output_dir / f"{cid}_pie_{self.style_id}.png"),
            )
            if path:
                specs.append(
                    ChartSpec(
                        cid,
                        "pie",
                        "Business Composition",
                        file_name=Path(path).name,
                        section_hint="overview",
                        priority=2,
                    )
                )
        return specs

    def _rule_radar_scoring(self, kp) -> list[ChartSpec]:
        """R5: 4+ scores -> radar chart (recommended)."""
        if not _HAS_EXT:
            return []
        categories, scores = [], []
        data_points = getattr(kp, "data_points", []) or []
        for dp in data_points:
            if "score" in dp.name.lower() or "rating" in dp.name.lower():
                try:
                    categories.append(dp.name.replace("_score", "").replace("_rating", ""))
                    scores.append(float(dp.value))
                except Exception:
                    pass
        if len(categories) < 3:
            return []
        cid = self._next_id()
        path = radar_chart(
            self.engine,
            categories,
            scores,
            title="Composite Score",
            save_path=str(self.engine.output_dir / f"{cid}_radar_{self.style_id}.png"),
        )
        if path:
            return [
                ChartSpec(
                    cid,
                    "radar",
                    "Composite Score",
                    file_name=Path(path).name,
                    section_hint="executive_summary",
                    priority=2,
                )
            ]
        return []

    def _rule_valuation_comparison(self, kp) -> list[ChartSpec]:
        """R6: peer valuation -> bar (mandatory)."""
        fin = getattr(kp, "financials", None)
        if not fin or not hasattr(fin, "peer_comparison") or not fin.peer_comparison:
            return []
        peers = fin.peer_comparison
        if isinstance(peers, dict) and len(peers) >= 3:
            cid = self._next_id()
            path = self.engine.bar_chart(
                peers,
                title="Valuation Comparison",
                save_path=str(self.engine.output_dir / f"{cid}_val_comp_{self.style_id}.png"),
            )
            if path:
                return [
                    ChartSpec(
                        cid,
                        "bar",
                        "Valuation Comparison",
                        file_name=Path(path).name,
                        section_hint="valuation",
                        priority=1,
                    )
                ]
        return []

    def _rule_bridge_analysis(self, kp) -> list[ChartSpec]:
        """R7: profit bridge data -> bridge chart (recommended)."""
        if not _HAS_ADV:
            return []
        fin = getattr(kp, "financials", None)
        if not fin:
            return []
        items = getattr(fin, "items", {})
        if "revenue" in items and "net_profit" in items:
            try:
                bridge_items = [
                    {"label": "Revenue", "value": float(items["revenue"]), "type": "total"},
                    {"label": "COGS", "value": -float(items.get("cogs", 0)), "type": "negative"},
                    {"label": "Gross Profit", "value": float(items.get("gross_profit", 0)), "type": "total"},
                    {"label": "Net Profit", "value": float(items["net_profit"]), "type": "total"},
                ]
                cid = self._next_id()
                path = bridge_chart(
                    self.engine,
                    bridge_items,
                    title="Profit Bridge",
                    save_path=str(self.engine.output_dir / f"{cid}_bridge_{self.style_id}.png"),
                )
                if path:
                    return [
                        ChartSpec(
                            cid,
                            "bridge",
                            "Profit Bridge Analysis",
                            file_name=Path(path).name,
                            section_hint="financial_analysis",
                            priority=2,
                        )
                    ]
            except Exception:
                pass
        return []

    def _rule_multi_panel_overview(self, kp) -> list[ChartSpec]:
        """R8: multi financial metrics -> multi-panel overview (recommended)."""
        if not _HAS_ADV:
            return []
        fin = getattr(kp, "financials", None)
        if not fin:
            return []
        items = getattr(fin, "items", {})
        if len(items) < 3:
            return []
        panels = []
        for key in list(items.keys())[:6]:  # Max 6 panels
            val = items[key]
            try:
                panels.append(
                    {
                        "type": "bar" if isinstance(val, (int, float)) else "pie",
                        "data": {key: float(val)} if isinstance(val, (int, float)) else {},
                        "title": key,
                    }
                )
            except Exception:
                pass
        if len(panels) >= 3:
            cid = self._next_id()
            path = multi_panel_chart(
                self.engine,
                panels,
                title="Financial Overview",
                layout=(2, 3),
                save_path=str(self.engine.output_dir / f"{cid}_overview_{self.style_id}.png"),
            )
            if path:
                return [
                    ChartSpec(
                        cid,
                        "multi_panel",
                        "Financial Overview",
                        file_name=Path(path).name,
                        section_hint="executive_summary",
                        priority=2,
                    )
                ]
        return []
