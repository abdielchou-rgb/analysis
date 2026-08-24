"""V53+ Production Chart Engine
=================================
Production-grade chart engine with institutional styling.

FP4 design:
  Senior analyst reports have zero naked pages.
  Every page has at least one data anchor; charts are visible judgment anchors.

Upgrades from V53:
  1. Figure numbering system (per-report, per-institution prefix)
  2. Data source footnotes on every chart
  3. Institution-specific grid/spine/annotation styling via chart_config
  4. Quality tiers: draft/review/final (varying DPI)
  5. Smart data label formatting (%/B/M/K auto)
  6. Remove inline STYLE_COLORS (delegated to chart_config)
"""
from __future__ import annotations
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from core.cn_font_setup import setup_cn_font, get_cn_font
setup_cn_font()  # Initialize Chinese font support

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("v51.chart_engine")

# Try to load annotation system
_HAS_ANNOTATIONS = False
try:
    from core.chart_annotations import (
        ChartAnnotation, ChartAnnotationSet, ChartAnnotator,
        AnnotationType, AnnotationSeverity,
        annotate_from_conviction, quick_annotate,
        make_valuation_zone, make_target_price_line,
        make_consensus_divergence, make_anomaly_callout,
        AnnotationIntelligence
    )
    _HAS_ANNOTATIONS = True
except ImportError:
    pass
except Exception as e:
    logger.debug(f"Chart annotations unavailable: {e}")

try:
    import matplotlib.ticker as mticker
    _HM = True
except ImportError:
    _HM = False

try:
    import numpy as np
    _HAS_NP = True
except ImportError:
    _HAS_NP = False

# ── Production chart engine ──────────────────────────────────────────

class ChartEngine:
    """Production-grade chart engine with institutional styling.

    Usage:
        engine = ChartEngine()
        engine.set_style("goldman_sachs")
        engine.bar_chart(data, "Revenue", "outputs/charts/revenue_bar.png")
        results = engine.generate_all({"Rev": 100, "Cost": 60}, "Company")
    """

    # Shared figure counter across all instances
    _global_figure_counter = 0

    def __init__(self, output_dir: str = "outputs/charts", style_id: str = "cicc",
                 quality: str = "final", data_source: str = ""):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.style_id = style_id
        self.generated = []
        self.quality = quality       # "draft"(72), "review"(150), "final"(200-300)
        self.data_source = data_source   # Default data source footnote
        self._figure_counter = 0     # Per-instance counter
        self._annotations_enabled = True  # V54: annotation system
        self._auto_annotate = True        # V54: auto-detect patterns
        self._conviction_data = None       # V54: ConvictionMatrix results

        # Try to use chart_config palette system
        try:
            from utils.chart_config import ensure_init, get_palette
            ensure_init()
            palette = get_palette(style_id)
            self.style = palette
            logger.info(f"ChartEngine initialized with {style_id} (chart_config)")
        except Exception:
            # Fallback to legacy STYLE_COLORS
            from core.chart_engine_legacy import get_chart_style
            self.style = get_chart_style(style_id)
            logger.info(f"ChartEngine initialized with {style_id} (legacy)")

    # ── Annotation configuration (V54) ─────────────────────────
    
    @property
    def annotator(self):
        """Get ChartAnnotator instance for current style."""
        if _HAS_ANNOTATIONS:
            return ChartAnnotator(self.style)
        return None
    
    def enable_annotations(self, enabled: bool = True):
        self._annotations_enabled = enabled
        return self
    
    def set_conviction_data(self, data: dict):
        self._conviction_data = data
        return self
    
    def _apply_annotations(self, ax, data: dict = None,
                           report_type: str = "company",
                           figure_num: int = None):
        """Apply judgment annotations to a chart axes."""
        if not _HAS_ANNOTATIONS or not self._annotations_enabled:
            return
        try:
            annotate_from_conviction(
                ax, self.style,
                data=data,
                conviction_data=self._conviction_data,
                report_type=report_type
            )
        except Exception as e:
            logger.debug(f"Annotations skipped: {e}")
    
    # ── Quality / DPI ──────────────────────────────────────────────

    @property
    def _dpi(self) -> int:
        return {"draft": 72, "review": 150, "final": 200}.get(self.quality, 200)

    def next_figure_num(self) -> int:
        self._figure_counter += 1
        return self._figure_counter

    # ── Style properties ───────────────────────────────────────────

    @property
    def colors(self) -> list[str]:
        return self.style.get("palette", ["#003366","#C41E3A","#E8C84C","#4CB8E8","#666666"])

    @property
    def primary(self) -> str:
        return self.style.get("primary", "#003366")

    @property
    def accent(self) -> str:
        return self.style.get("accent", "#C41E3A")

    def set_style(self, style_id: str):
        """Set chart style by institution name."""
        self.style_id = style_id
        try:
            from utils.chart_config import get_palette
            palette = get_palette(style_id)
            self.style = palette
        except Exception:
            from core.chart_engine_legacy import get_chart_style
            self.style = get_chart_style(style_id)
        return self

    def _save(self, fig, save_path: str = None, default_name: str = "") -> str:
        """Save figure and register generated path."""
        path = save_path or str(self.output_dir / default_name)
        fig.savefig(path, dpi=self._dpi, bbox_inches="tight", pad_inches=0.3,
                    facecolor=self.style.get("bg", "#FFFFFF"), edgecolor="none")
        plt.close(fig)
        self.generated.append(path)
        logger.debug(f"Chart saved: {path}")
        return path

    def _apply_style(self, ax, title: str = "", figure_num: int = None,
                     data_source: str = ""):
        """Apply institution-specific styling with optional figure number and source."""
        try:
            from utils.chart_config import apply_institution_style
            apply_institution_style(ax, self.style, title, figure_num,
                                    data_source or self.data_source)
        except Exception:
            # Fallback basic styling
            if title:
                ax.set_title(title, fontsize=12, fontweight="bold", color=self.primary, pad=12)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)
            ax.set_axisbelow(True)
            ax.set_facecolor(self.style.get("bg", "#FFFFFF"))
            ax.tick_params(colors=self.style.get("text", "#333333"), labelsize=8)

    # ── Bar chart ──────────────────────────────────────────────────

    def bar_chart(self, data: dict, title: str = "", save_path: str = "",
                  data_source: str = "", figure_num: int = None,
                  horizontal: bool = False) -> Optional[str]:
        try:
            keys = list(data.keys()); vals = list(data.values())
            fig, ax = plt.subplots(figsize=(9, max(4, len(keys) * 0.4)))
            colors = self.colors[:len(keys)]

            if horizontal:
                bars = ax.barh(range(len(keys)), vals, color=colors, height=0.55,
                               edgecolor="white", linewidth=0.5)
                ax.set_yticks(range(len(keys))); ax.set_yticklabels(keys, fontsize=9)
                for i, (k, v) in enumerate(zip(keys, vals)):
                    ax.text(v + max(vals)*0.01, i, f"{v:.1f}", ha="left", va="center",
                            fontsize=7.5, color=self.style.get("text", "#333333"))
            else:
                bars = ax.bar(range(len(keys)), vals, color=colors, width=0.55,
                              edgecolor="white", linewidth=0.5)
                ax.set_xticks(range(len(keys))); ax.set_xticklabels(keys, rotation=25, ha="right", fontsize=8)
                for i, (k, v) in enumerate(zip(keys, vals)):
                    ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=7.5,
                            color=self.style.get("text", "#333333"))

            self._apply_style(ax, title, figure_num, data_source)
            # V54: Add analyst judgment annotations
            if _HAS_ANNOTATIONS:
                try:
                    data_dict = dict(zip(keys, vals))
                    if data_dict and len(data_dict) >= 2:
                        self._apply_annotations(ax, data=data_dict)
                except Exception:
                    pass
            path = self._save(fig, save_path, f"bar_{self.style_id}.png")
            return path
        except Exception as e:
            logger.warning(f"Bar chart failed: {e}"); return None

    # ── Line chart ─────────────────────────────────────────────────

    def line_chart(self, data: dict, title: str = "", save_path: str = "",
                   data_source: str = "", figure_num: int = None,
                   marker: str = "o", show_fill: bool = True) -> Optional[str]:
        try:
            keys = list(data.keys()); vals = list(data.values())
            fig, ax = plt.subplots(figsize=(9, 5))
            ax.plot(range(len(vals)), vals, color=self.colors[0], linewidth=2.5,
                    marker=marker, markersize=5, markerfacecolor=self.colors[0])
            if show_fill:
                ax.fill_between(range(len(vals)), vals, alpha=0.08, color=self.colors[0])
            ax.set_xticks(range(len(keys))); ax.set_xticklabels(keys, rotation=25, ha="right", fontsize=8)

            # Annotate start, end, max, min
            if vals:
                max_idx, min_idx = vals.index(max(vals)), vals.index(min(vals))
                for idx, label, offset in [(0, "Start", -8), (-1, "End", 8),
                                           (max_idx, "Peak", -10), (min_idx, "Trough", 10)]:
                    if idx == max_idx or idx == min_idx or idx == 0 or idx == len(vals)-1:
                        ax.annotate(f"{vals[idx]:.1f}", (idx, vals[idx]),
                                    textcoords="offset points", xytext=(0, offset),
                                    ha="center", fontsize=7, color=self.style.get("text", "#555555"))

            self._apply_style(ax, title, figure_num, data_source)
            # V54: Add analyst judgment annotations
            if _HAS_ANNOTATIONS:
                try:
                    data_dict = dict(zip(keys, vals))
                    if data_dict and len(data_dict) >= 2:
                        self._apply_annotations(ax, data=data_dict)
                except Exception:
                    pass
            path = self._save(fig, save_path, f"line_{self.style_id}.png")
            return path
        except Exception as e:
            logger.warning(f"Line chart failed: {e}"); return None

    # ── Pie chart ──────────────────────────────────────────────────

    def pie_chart(self, data: dict, title: str = "", save_path: str = "",
                  data_source: str = "", figure_num: int = None) -> Optional[str]:
        try:
            keys = list(data.keys()); vals = list(data.values())
            fig, ax = plt.subplots(figsize=(7, 6))
            colors = self.colors[:len(keys)]

            # Donut style (more professional)
            wedges, texts, autotexts = ax.pie(
                vals, labels=keys, autopct=lambda p: f"{p:.1f}%" if p >= 3 else "",
                colors=colors, startangle=90, pctdistance=0.75,
                wedgeprops={"linewidth": 0.8, "edgecolor": "white"},
                textprops={"fontsize": 9})

            # Add center label
            ax.text(0, 0, f"Total\n{sum(vals):.0f}", ha="center", va="center",
                    fontsize=11, fontweight="bold", color=self.style.get("text", "#333333"))

            self._apply_style(ax, title, figure_num, data_source)
            # V54: Add analyst judgment annotations
            if _HAS_ANNOTATIONS:
                try:
                    data_dict = dict(zip(keys, vals))
                    if data_dict and len(data_dict) >= 2:
                        self._apply_annotations(ax, data=data_dict)
                except Exception:
                    pass
            path = self._save(fig, save_path, f"pie_{self.style_id}.png")
            return path
        except Exception as e:
            logger.warning(f"Pie chart failed: {e}"); return None

    # ── Waterfall chart ────────────────────────────────────────────

    def waterfall_chart(self, breakdown, title: str = "\u6536\u5165\u62c6\u89e3",
                        save_path: str = "", data_source: str = "",
                        figure_num: int = None) -> Optional[str]:
        """Waterfall for income/profit bridge analysis.
        breakdown: list of dicts [{"label": "...", "value": 100}, ...]
        First item is total start, last item is total end.
        """
        try:
            # Accept both list[dict] and flat dict
            if isinstance(breakdown, dict):
                items = [{"label": k, "value": v} for k, v in breakdown.items()]
            else:
                items = breakdown

            labels = [it["label"] for it in items]
            values = [it["value"] for it in items]

            fig, ax = plt.subplots(figsize=(10, 5.5))
            n = len(values)
            bar_colors = []
            running = [0] * n
            bottoms = [0] * n

            for i in range(n):
                if i == 0:
                    bottoms[i] = 0
                    running[i] = values[i]
                    bar_colors.append(self.colors[0])
                else:
                    running[i] = running[i-1] + values[i]
                    bottoms[i] = min(running[i-1], running[i])
                    if values[i] >= 0:
                        bar_colors.append(self.style.get("positive", self.colors[1]))
                    else:
                        bar_colors.append(self.style.get("negative", self.colors[2]))

            ax.bar(range(n), [abs(v) if i > 0 else v for i, v in enumerate(values)],
                   bottom=bottoms, color=bar_colors, width=0.6,
                   edgecolor="white", linewidth=0.5)

            for i in range(n):
                val = values[i]
                y_pos = running[i] + (abs(val)*0.05 if val >= 0 else -abs(val)*0.08)
                color = "white" if abs(val) > 50 else self.style.get("text", "#333333")
                ax.text(i, y_pos, f"{val:+.1f}" if i > 0 else f"{val:.1f}",
                        ha="center", va="center", fontsize=8, fontweight="bold", color=color)

            ax.set_xticks(range(n)); ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
            self._apply_style(ax, title, figure_num, data_source)

            # Add connecting line for running total
            ax.plot(range(n), running, color=self.style.get("secondary", "#666666"),
                    linewidth=1, linestyle="--", alpha=0.5)

            path = self._save(fig, save_path, f"waterfall_{self.style_id}.png")
            return path
        except Exception as e:
            logger.warning(f"Waterfall failed: {e}"); return None

    # ── Sensitivity heatmap ────────────────────────────────────────

    def sensitivity_heatmap(self, matrix, rows=None, cols=None,
                           title: str = "\u654f\u611f\u6027\u5206\u6790",
                           save_path: str = "", data_source: str = "",
                           figure_num: int = None) -> Optional[str]:
        if not _HAS_NP:
            logger.warning("Heatmap requires numpy"); return None
        try:
            if isinstance(matrix, list) and rows and cols:
                data = np.array(matrix)
            else:
                data = np.array(matrix) if isinstance(matrix, (list, np.ndarray)) else np.zeros((5, 5))
                if rows is None: rows = [f"R{i+1}" for i in range(data.shape[0])]
                if cols is None: cols = [f"C{i+1}" for i in range(data.shape[1])]

            fig, ax = plt.subplots(figsize=(9, 7))
            im = ax.imshow(data, cmap="RdYlGn_r", aspect="auto", interpolation="nearest")
            plt.colorbar(im, ax=ax, shrink=0.7, label="Value")

            ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, rotation=25, ha="right", fontsize=8)
            ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows, fontsize=9)

            for i in range(len(rows)):
                for j in range(len(cols)):
                    ax.text(j, i, f"{data[i,j]:.2f}", ha="center", va="center",
                            fontsize=8, color="white" if abs(data[i,j]) > 0.5 else "black",
                            fontweight="bold")

            self._apply_style(ax, title, figure_num, data_source)
            # V54: Add analyst judgment annotations
            if _HAS_ANNOTATIONS:
                try:
                    data_dict = dict(zip(keys, vals))
                    if data_dict and len(data_dict) >= 2:
                        self._apply_annotations(ax, data=data_dict)
                except Exception:
                    pass
            path = self._save(fig, save_path, f"sensitivity_{self.style_id}.png")
            return path
        except Exception as e:
            logger.warning(f"Heatmap failed: {e}"); return None

    # ── Pareto chart ───────────────────────────────────────────────

    def pareto_chart(self, data: dict, title: str = "\u5e15\u7d2f\u6258\u5206\u6790",
                     save_path: str = "", data_source: str = "",
                     figure_num: int = None) -> Optional[str]:
        try:
            sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)
            keys = [k for k, v in sorted_items]; vals = [v for k, v in sorted_items]
            total = sum(vals); cumulative = [sum(vals[:i+1])/total*100 for i in range(len(vals))]

            fig, ax1 = plt.subplots(figsize=(9, 5))
            bars = ax1.bar(range(len(keys)), vals, color=self.colors[0], width=0.5, alpha=0.8)
            ax1.set_ylabel("Value", fontsize=10, color=self.primary)
            ax1.set_xticks(range(len(keys))); ax1.set_xticklabels(keys, rotation=25, ha="right", fontsize=8)

            ax2 = ax1.twinx()
            ax2.plot(range(len(cumulative)), cumulative, color=self.accent, marker="o", linewidth=2, markersize=6)
            ax2.set_ylabel("Cumulative %", fontsize=10, color=self.accent)
            ax2.axhline(y=80, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)

            for i, (k, v) in enumerate(zip(keys, vals)):
                ax1.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=7)
            for i, c in enumerate(cumulative):
                ax2.text(i, c+2, f"{c:.0f}%", ha="center", fontsize=7, color=self.accent)

            self._apply_style(ax1, title, figure_num, data_source)

        # V54: Add analyst judgment annotations
            # V54: Add analyst judgment annotations
            if _HAS_ANNOTATIONS:
                try:
                    try:
                        data_dict = dict(zip(keys, vals))
                        if data_dict and len(data_dict) >= 2:
                            self._apply_annotations(ax, data=data_dict)
                    except Exception:
                        pass
                except Exception:
                    pass
            try:
                data_dict = dict(zip(keys, vals)) if "keys" in locals() else None
                if data_dict and len(data_dict) >= 2:
                    self._apply_annotations(ax, data=data_dict)
            except Exception:
                pass
            path = self._save(fig, save_path, f"pareto_{self.style_id}.png")
            return path
        except Exception as e:
            logger.warning(f"Pareto failed: {e}"); return None

    # ── Embed to Markdown ──────────────────────────────────────────

    def embed_to_markdown(self, paths: list[str] = None) -> str:
        paths = paths or self.generated
        if not paths:
            return ""
        lines = ["\n\n---\n**Data Visualization**\n"]
        for i, p in enumerate(paths, 1):
            rel = Path(p).name
            prefix = self.style.get("figure_prefix", "Figure ")
            sep = self.style.get("figure_separator", ": ")
            lines.append(f"![{prefix}{i}{sep}{Path(p).stem.replace('_',' ').title()}]({rel})")
            lines.append(f"*{prefix}{i}{sep}{Path(p).stem.replace('_',' ').title()}*\n")
        return "\n".join(lines)

    # ── Generate all ───────────────────────────────────────────────

    def generate_all(self, data: dict, title_prefix: str = "",
                     style_id: str = "", report_text: str = "",
                     data_source: str = "") -> dict[str, str]:
        if style_id:
            self.set_style(style_id)
        paths = {}
        figure_num = self.next_figure_num()

        if len(data) >= 2:
            bar = self.bar_chart(data, f"{title_prefix} \u6838\u5fc3\u6307\u6807",
                                 figure_num=figure_num, data_source=data_source)
            if bar: paths["bar"] = bar; figure_num = self.next_figure_num()
            pie = self.pie_chart(data, f"{title_prefix} \u6784\u6210",
                                 figure_num=figure_num, data_source=data_source)
            if pie: paths["pie"] = pie; figure_num = self.next_figure_num()
            pareto = self.pareto_chart(data, f"{title_prefix} \u5e15\u7d2f\u6258",
                                       figure_num=figure_num, data_source=data_source)
            if pareto: paths["pareto"] = pareto; figure_num = self.next_figure_num()

        if len(data) >= 4:
            line = self.line_chart(data, f"{title_prefix} \u8d8b\u52bf",
                                   figure_num=figure_num, data_source=data_source)
            if line: paths["line"] = line; figure_num = self.next_figure_num()

        return paths

    # ── extract_and_generate (classmethod) ─────────────────────────

    # Mapping: table header keywords → chart type
    _HEADER_CHART_MAP: list[tuple[list[str], str]] = [
        (["价格", "走势", "趋势", "股价", "收盘", "变动", "变化", "增速", "增长"], "line"),
        (["营收", "结构", "占比", "%", "构成", "分布", "比重", "份额结构"], "pie"),
        (["季度", "利润", "净利润", "同比", "环比", "收入", "毛利", "费用", "现金流",
          "资产", "负债", "权益", "ROE", "ROA", "EPS", "毛利率", "净利率",
          "营收规模", "各业务", "分业务", "业务板块"], "bar"),
        (["竞争", "格局", "产能", "市占", "市场份额", "排名", "集中度",
          "出货量", "装机量", "销量排名", "品牌"], "barh"),
        (["情景", "估值", "敏感性", "WACC", "永续增长", "Exit", "目标价",
          "假设矩阵", "压力测试", "多因子"], "sensitivity"),
    ]

    @classmethod
    def _parse_md_table(cls, md_text: str) -> list[dict]:
        """Parse Markdown tables from report text.

        Returns a list of dicts: [{headers, rows, raw_text}, ...].
        Each row is a list of cell strings.
        """
        tables = []
        # Match Markdown table blocks line by line to keep tables separate.
        # Strategy: find header+separator, then consume consecutive data rows until
        # we hit a blank line or a non-pipe line.
        lines = md_text.split("\n")
        i = 0
        while i < len(lines) - 2:
            line = lines[i].strip()
            # Look for a table header line: starts with | and has content
            if not line.startswith("|"):
                i += 1
                continue
            # Next line must be a separator line: |---|:--| etc.
            sep_line = lines[i + 1].strip()
            if not re.match(r'^\|[-:\s|]+\|$', sep_line):
                i += 1
                continue

            headers = [h.strip() for h in line.split("|") if h.strip() != ""]
            if not headers:
                i += 1
                continue

            # Collect data rows until we hit a blank line or non-pipe line
            rows = []
            j = i + 2
            while j < len(lines):
                row_line = lines[j].strip()
                if not row_line.startswith("|"):
                    break  # blank line or non-table content
                cells = [c.strip() for c in row_line.split("|") if c.strip() != ""]
                if cells:
                    rows.append(cells)
                j += 1

            if rows:
                raw_text = "\n".join(lines[i:j])
                tables.append({
                    "headers": headers,
                    "rows": rows,
                    "raw_text": raw_text,
                })

            i = j  # skip past consumed rows
        return tables

    @classmethod
    def _infer_chart_type(cls, headers: list[str]) -> str:
        """Infer chart type from table header keywords."""
        header_text = " ".join(headers).lower()
        scores: dict[str, int] = {}
        for keywords, chart_type in cls._HEADER_CHART_MAP:
            score = sum(1 for kw in keywords if kw.lower() in header_text)
            if score > 0:
                scores[chart_type] = scores.get(chart_type, 0) + score
        if not scores:
            return "bar"  # default fallback
        return max(scores, key=lambda k: scores[k])

    @classmethod
    def _extract_data_from_table(cls, table: dict) -> dict[str, float] | None:
        """Extract numeric key→value pairs from a parsed table.

        For bar/line/pie: returns {label_col: numeric_col}.
        For barh: same but with horizontal semantics.
        """
        headers = table["headers"]
        rows = table["rows"]
        if len(headers) < 2 or not rows:
            return None

        # Find the numeric column (prioritize rightmost numeric column, skip label col)
        numeric_col_idx = -1
        for j in range(len(headers) - 1, 0, -1):
            # Check if this column's data is mostly numeric
            numeric_count = 0
            for row in rows:
                if j < len(row):
                    val = row[j].replace(",", "").replace("，", "").replace("%", "").strip()
                    try:
                        float(val)
                        numeric_count += 1
                    except ValueError:
                        pass
            if numeric_count >= len(rows) * 0.5:  # majority numeric
                numeric_col_idx = j
                break

        if numeric_col_idx < 0:
            return None

        result: dict[str, float] = {}
        for row in rows:
            if len(row) <= numeric_col_idx:
                continue
            label = row[0]
            val_str = row[numeric_col_idx].replace(",", "").replace("，", "").replace("%", "").strip()
            try:
                result[label] = float(val_str)
            except ValueError:
                continue

        return result if result else None

    @classmethod
    def _extract_sensitivity_matrix(cls, table: dict) -> tuple[list, list, list] | None:
        """Extract a sensitivity matrix: (row_labels, col_labels, matrix_2d)."""
        headers = table["headers"]
        rows = table["rows"]
        if len(headers) < 2 or len(rows) < 2:
            return None

        row_labels = []
        col_labels = headers[1:]  # first header is row label header
        matrix = []

        for row in rows:
            if len(row) < 2:
                continue
            row_labels.append(row[0])
            numeric_row = []
            for j in range(1, min(len(row), len(headers))):
                val_str = row[j].replace(",", "").replace("，", "").replace("%", "").strip()
                try:
                    numeric_row.append(float(val_str))
                except ValueError:
                    numeric_row.append(0.0)
            if numeric_row:
                matrix.append(numeric_row)

        if row_labels and col_labels and matrix:
            # Pad uneven rows
            max_cols = max(len(r) for r in matrix)
            for r in matrix:
                while len(r) < max_cols:
                    r.append(0.0)
            return row_labels, col_labels[:max_cols], matrix
        return None

    @classmethod
    def extract_and_generate(
        cls,
        md_text: str,
        style_id: str = "cicc",
        output_dir: str = None,
    ) -> dict[str, str]:
        """Extract structured data from MD report text and generate charts.

        Parses Markdown tables from the report, infers chart type from
        header semantics, constructs KnowledgePackage entries, and
        generates institutional-quality charts.

        Args:
            md_text: Full markdown report text containing tables.
            style_id: Institution style (cicc, goldman_sachs, etc.).
            output_dir: Output directory for chart PNGs. Defaults to
                        'outputs/charts'.

        Returns:
            dict mapping chart type label → absolute PNG path, e.g.:
            {"bar": ".../bar_cicc.png", "pie": ".../pie_cicc.png"}
        """
        tables = cls._parse_md_table(md_text)
        if not tables:
            logger.info("extract_and_generate: no Markdown tables found")
            return {}

        out_dir = output_dir or "outputs/charts"
        engine = ChartEngine(output_dir=out_dir, style_id=style_id)

        chart_paths: dict[str, str] = {}

        for table in tables:
            chart_type = cls._infer_chart_type(table["headers"])

            if chart_type == "sensitivity":
                mat = cls._extract_sensitivity_matrix(table)
                if mat is None:
                    continue
                row_labels, col_labels, matrix = mat
                # Build a title from the first 2-3 headers
                title_parts = table["headers"][:3]
                title = " ".join(title_parts) if title_parts else "敏感性分析"
                path = engine.sensitivity_heatmap(
                    matrix, row_labels, col_labels,
                    title=title,
                )
                if path:
                    chart_paths["sensitivity"] = path
                    logger.info(f"extract_and_generate: sensitivity → {path}")
                continue

            data = cls._extract_data_from_table(table)
            if data is None or len(data) < 2:
                continue

            # Build a title from first meaningful header
            title_header = table["headers"][0] if table["headers"] else "Key Metrics"

            if chart_type == "line":
                path = engine.line_chart(data, title=f"{title_header} \u8d8b\u52bf")
                if path:
                    chart_paths["line"] = path
            elif chart_type == "pie":
                path = engine.pie_chart(data, title=f"{title_header} \u6784\u6210")
                if path:
                    chart_paths["pie"] = path
            elif chart_type == "bar":
                path = engine.bar_chart(data, title=f"{title_header} \u5bf9\u6bd4")
                if path:
                    chart_paths["bar"] = path
            elif chart_type == "barh":
                path = engine.bar_chart(
                    data, title=f"{title_header} \u5bf9\u6bd4",
                    horizontal=True,
                )
                if path:
                    chart_paths["barh"] = path

            logger.info(
                f"extract_and_generate: {chart_type} ({len(data)} pts) "
                f"from table header '{title_header}'"
            )

        return chart_paths

# ── Convenience functions ────────────────────────────────────────────

def quick_charts(data: dict, style_id: str = "cicc", prefix: str = "",
                 data_source: str = "") -> dict[str, str]:
    engine = ChartEngine(style_id=style_id, data_source=data_source)
    return engine.generate_all(data, prefix, style_id)

def sensitivity_quick(matrix, rows, cols, style_id: str = "cicc") -> Optional[str]:
    engine = ChartEngine(style_id=style_id)
    return engine.sensitivity_heatmap(matrix, rows, cols)
