"""V53+ Advanced Financial Charts - Production grade.
Candlestick, Dot Plot, Sensitivity Table, Multi-Panel, Bridge Chart.
All functions use ChartEngine instance for institutional styling.
"""
from core.cn_font_setup import setup_cn_font, get_cn_font
setup_cn_font()  # Initialize Chinese font support
import numpy as np
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("v53.advanced_charts")


def candlestick_chart(engine, ohlc_data: list[dict],
                      title: str = "Price Trend",
                      save_path: str = "", data_source: str = "",
                      figure_num: int = None,
                      volume_data: list[float] = None) -> Optional[str]:
    """Candlestick chart for stock price technical analysis.

    ohlc_data: [{"date": "2024-01", "open": 100, "high": 105, "low": 98, "close": 103}, ...]
    volume_data: optional list of volume values matching ohlc_data length
    """
    if not ohlc_data or len(ohlc_data) < 2:
        return None
    try:
        dates = [d["date"] for d in ohlc_data]
        opens = [d["open"] for d in ohlc_data]
        highs = [d["high"] for d in ohlc_data]
        lows = [d["low"] for d in ohlc_data]
        closes = [d["close"] for d in ohlc_data]

        n = len(ohlc_data)
        up_color = engine.style.get("positive", "#009688")
        down_color = engine.style.get("negative", "#C41E3A")
        width = 0.6

        if volume_data:
            fig, (ax, ax_vol) = plt.subplots(2, 1, figsize=(12, 7),
                                              gridspec_kw={"height_ratios": [3, 1]})
        else:
            fig, ax = plt.subplots(figsize=(12, 6))

        for i in range(n):
            color = up_color if closes[i] >= opens[i] else down_color
            # High-low line
            ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=1)
            # Open-close rectangle
            rect = plt.Rectangle((i - width/2, min(opens[i], closes[i])),
                                  width, abs(closes[i] - opens[i]) or 0.5,
                                  facecolor=color, edgecolor=color, alpha=0.8)
            ax.add_patch(rect)

        # Volume bars
        if volume_data and len(volume_data) == n:
            vol_colors = [up_color if closes[i] >= opens[i] else down_color for i in range(n)]
            ax_vol.bar(range(n), volume_data, color=vol_colors, alpha=0.5, width=0.8)
            ax_vol.set_ylabel("Volume", fontsize=9)
            ax_vol.set_xticks(range(n))
            ax_vol.set_xticklabels(dates, rotation=30, ha="right", fontsize=7)
            try:
                from utils.chart_config import apply_institution_style
                apply_institution_style(ax_vol, engine.style, "", None, data_source)
            except Exception:
                ax_vol.spines["top"].set_visible(False)
        else:
            ax.set_xticks(range(n))
            ax.set_xticklabels(dates, rotation=30, ha="right", fontsize=8)

        # Auto-scale
        ax.autoscale_view()
        ax.set_ylabel("Price", fontsize=10)

        try:
            from utils.chart_config import apply_institution_style
            apply_institution_style(ax, engine.style, title, figure_num, data_source)
        except Exception:
            ax.set_title(title, fontsize=13, fontweight="bold",
                         color=engine.style.get("primary", "#003366"), pad=12)

        path = save_path or str(engine.output_dir / f"candlestick_{engine.style_id}.png")
        plt.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close()
        engine.generated.append(path)
        return path
    except Exception as e:
        logger.warning(f"Candlestick chart failed: {e}")
        return None


def dotplot_chart(engine, data_points: list[dict],
                  title: str = "Forecast Distribution",
                  save_path: str = "", data_source: str = "",
                  figure_num: int = None) -> Optional[str]:
    """Dot plot showing distribution of analyst forecasts.

    data_points: [
        {"label": "2024E", "value": 4.5, "median": 4.25, "range": [3.5, 5.0]},
        {"label": "2025E", "value": 3.75, "median": 3.5, "range": [2.8, 4.5]},
    ]
    Shows individual forecasts as dots, median as line, IQR as shaded band.
    """
    if not data_points:
        return None
    try:
        labels = [d["label"] for d in data_points]
        n = len(labels)
        primary = engine.style.get("primary", "#003366")
        accent = engine.style.get("accent", "#C41E3A")

        fig, ax = plt.subplots(figsize=(10, 6))

        for i, dp in enumerate(data_points):
            y = i + 1
            # IQR range band
            if "range" in dp and len(dp["range"]) == 2:
                ax.fill_betweenx([y-0.3, y+0.3], dp["range"][0], dp["range"][1],
                                 alpha=0.12, color=accent)
            # Median line
            if "median" in dp:
                ax.plot(dp["median"], y, marker="D", color=primary,
                        markersize=8, zorder=4)
            # Individual dots (simulated around the value)
            if "values" in dp:
                vals = dp["values"]
                jitter = np.random.normal(0, 0.05, size=len(vals))
                ax.scatter(vals, np.full(len(vals), y) + jitter,
                          alpha=0.5, s=15, color=accent, zorder=3)
            # Current forecast
            if "value" in dp:
                ax.scatter(dp["value"], y, marker="o", color=primary,
                          s=80, zorder=5, edgecolor="white", linewidth=1)

        ax.set_yticks(range(1, n+1))
        ax.set_yticklabels(labels, fontsize=10)
        ax.axvline(x=0, color="gray", linestyle="--", alpha=0.3)

        try:
            from utils.chart_config import apply_institution_style
            apply_institution_style(ax, engine.style, title, figure_num, data_source)
        except Exception:
            ax.set_title(title, fontsize=13, fontweight="bold", color=primary, pad=12)

        path = save_path or str(engine.output_dir / f"dotplot_{engine.style_id}.png")
        plt.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close()
        engine.generated.append(path)
        return path
    except Exception as e:
        logger.warning(f"Dot plot failed: {e}")
        return None


def multi_panel_chart(engine, panels: list[dict],
                      title: str = "",
                      save_path: str = "", data_source: str = "",
                      figure_num: int = None,
                      layout: tuple = None) -> Optional[str]:
    """Multi-panel chart grid for comprehensive analysis display.

    panels: [
        {"type": "bar", "data": {"A": 10, "B": 20}, "title": "Revenue"},
        {"type": "line", "data": {"2020": 10, "2021": 15}, "title": "Trend"},
    ]
    layout: (rows, cols) - auto-calculated if None
    """
    if not panels:
        return None
    try:
        n = len(panels)
        if layout:
            rows, cols = layout
        elif n <= 2:
            rows, cols = 1, n
        elif n <= 4:
            rows, cols = 2, 2
        else:
            rows, cols = 3, 3

        fig, axes = plt.subplots(rows, cols, figsize=(5*cols, 4*rows))
        axes_flat = axes.flatten() if hasattr(axes, "flatten") else [axes]

        primary = engine.style.get("primary", "#003366")
        palette = engine.style.get("palette", ["#003366", "#C41E3A"])

        for idx, panel in enumerate(panels):
            if idx >= len(axes_flat):
                break
            ax = axes_flat[idx]
            data = panel.get("data", {})
            ptype = panel.get("type", "bar")
            ptitle = panel.get("title", f"Panel {idx+1}")

            keys = list(data.keys())
            vals = list(data.values())

            if ptype == "bar":
                ax.bar(range(len(keys)), vals, color=palette[0], width=0.5,
                       edgecolor="white", linewidth=0.5)
                ax.set_xticks(range(len(keys)))
                ax.set_xticklabels(keys, rotation=20, ha="right", fontsize=7)

            elif ptype == "line":
                ax.plot(range(len(vals)), vals, color=palette[0], linewidth=2,
                        marker="o", markersize=4)
                ax.set_xticks(range(len(keys)))
                ax.set_xticklabels(keys, rotation=20, ha="right", fontsize=7)

            elif ptype == "pie":
                colors = palette[:len(keys)]
                ax.pie(vals, labels=keys, autopct=lambda p: f"{p:.0f}%" if p >= 5 else "",
                       colors=colors, startangle=90, textprops={"fontsize": 8})

            elif ptype == "scatter":
                if len(keys) == len(vals) and len(vals) > 0:
                    x = list(range(len(vals)))
                    ax.scatter(x, vals, color=palette[0], s=30, alpha=0.7)

            eq_style = panel.get("equal_axis", True)
            if eq_style:
                ax.set_aspect("auto")

            ax.set_title(ptitle, fontsize=10, fontweight="bold", color=primary)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        # Hide unused axes
        for idx in range(len(panels), len(axes_flat)):
            axes_flat[idx].set_visible(False)

        if title:
            fig.suptitle(title, fontsize=14, fontweight="bold", y=1.02)

        path = save_path or str(engine.output_dir / f"multipanel_{engine.style_id}.png")
        plt.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close()
        engine.generated.append(path)
        return path
    except Exception as e:
        logger.warning(f"Multi-panel chart failed: {e}")
        return None


def sensitivity_table_heatmap(engine, matrix: dict, x_labels: list[str],
                               y_labels: list[str],
                               title: str = "Sensitivity Analysis",
                               save_path: str = "", data_source: str = "",
                               figure_num: int = None) -> Optional[str]:
    """Professional sensitivity table as heatmap.

    matrix: {(x_idx, y_idx): value} or 2D list
    x_labels/y_labels: axis labels (e.g. WACC values, growth rates)
    """
    try:
        ny, nx = len(y_labels), len(x_labels)

        # Build 2D array
        data = np.zeros((ny, nx))
        if isinstance(matrix, dict):
            for (xi, yi), val in matrix.items():
                if xi < nx and yi < ny:
                    data[yi, xi] = val
        elif isinstance(matrix, (list, np.ndarray)):
            data = np.array(matrix)

        fig, ax = plt.subplots(figsize=(max(8, nx*1.2), max(6, ny*0.8)))

        # Custom colormap (RdYlGn for financial)
        cmap = plt.cm.RdYlGn_r
        im = ax.imshow(data, cmap=cmap, aspect="auto", interpolation="nearest")

        # Colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
        cbar.set_label("Valuation", fontsize=9)

        # Tick labels
        ax.set_xticks(range(nx))
        ax.set_xticklabels(x_labels, rotation=0, fontsize=8)
        ax.set_yticks(range(ny))
        ax.set_yticklabels(y_labels, fontsize=8)

        # Cell annotations
        data_min, data_max = data.min(), data.max()
        for i in range(ny):
            for j in range(nx):
                val = data[i, j]
                color = "white" if abs(val - data_min) > 0.3 * (data_max - data_min) else "black"
                ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                        fontsize=9, fontweight="bold", color=color)

        # Axis labels
        if x_labels:
            ax.set_xlabel(x_labels[0].split("=")[0] if "=" in x_labels[0] else "",
                          fontsize=10, fontweight="bold",
                          color=engine.style.get("primary", "#003366"))
        ax.xaxis.set_label_position("top")
        ax.xaxis.tick_top()

        try:
            from utils.chart_config import apply_institution_style
            apply_institution_style(ax, engine.style, title, figure_num, data_source)
        except Exception:
            ax.set_title(title, fontsize=13, fontweight="bold",
                         color=engine.style.get("primary", "#003366"), pad=12)

        path = save_path or str(engine.output_dir / f"sensitivity_table_{engine.style_id}.png")
        plt.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close()
        engine.generated.append(path)
        return path
    except Exception as e:
        logger.warning(f"Sensitivity table failed: {e}")
        return None


def bridge_chart(engine, items: list[dict],
                 title: str = "Profit Bridge Analysis",
                 save_path: str = "", data_source: str = "",
                 figure_num: int = None) -> Optional[str]:
    """Bridge chart (enhanced waterfall) for YoY variance analysis.

    items: [
        {"label": "2023 Revenue", "value": 100, "type": "total"},
        {"label": "Volume", "value": 15, "type": "positive"},
        {"label": "Price", "value": -5, "type": "negative"},
        {"label": "Mix", "value": 8, "type": "positive"},
        {"label": "FX", "value": -3, "type": "negative"},
        {"label": "2024 Revenue", "value": 115, "type": "total"},
    ]
    """
    if not items or len(items) < 2:
        return None
    try:
        labels = [it["label"] for it in items]
        values = [it["value"] for it in items]
        types = [it.get("type", "positive") for it in items]
        n = len(items)

        primary = engine.style.get("primary", "#003366")
        positive = engine.style.get("positive", "#009688")
        negative = engine.style.get("negative", "#C41E3A")

        fig, ax = plt.subplots(figsize=(11, 6))

        # Calculate running total
        running = [0] * n
        bottoms = [0] * n
        bar_colors = []

        for i in range(n):
            if types[i] == "total":
                if i == 0:
                    running[i] = values[i]
                    bottoms[i] = 0
                else:
                    bottoms[i] = 0
                    running[i] = values[i]
                bar_colors.append(primary)
            elif types[i] == "positive":
                bottoms[i] = running[i-1]
                running[i] = running[i-1] + values[i]
                bar_colors.append(positive)
            else:
                bottoms[i] = running[i-1] + values[i]
                running[i] = running[i-1] + values[i]
                bar_colors.append(negative)

        bar_heights = []
        for i in range(n):
            if types[i] == "total":
                bar_heights.append(values[i])
            else:
                bar_heights.append(abs(values[i]))

        ax.bar(range(n), bar_heights, bottom=bottoms, color=bar_colors,
               width=0.6, edgecolor="white", linewidth=0.5)

        # Labels on bars
        for i in range(n):
            if types[i] == "total":
                y_pos = running[i] + max(values)*0.03
                ax.text(i, y_pos, f"{values[i]:.0f}", ha="center", va="bottom",
                        fontsize=9, fontweight="bold", color=primary)
            else:
                direction = "positive" if types[i] == "positive" else "negative"
                offset = 0.05 if direction == "positive" else -0.08
                color = positive if direction == "positive" else negative
                ax.text(i, running[i] + abs(values[i])*offset, f"{values[i]:+.0f}",
                        ha="center", va="center", fontsize=8, fontweight="bold", color=color)

        # Connecting line
        ax.plot(range(n), running, color=primary, linewidth=1.2, linestyle="--", alpha=0.4)

        ax.set_xticks(range(n))
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)

        try:
            from utils.chart_config import apply_institution_style
            apply_institution_style(ax, engine.style, title, figure_num, data_source)
        except Exception:
            ax.set_title(title, fontsize=13, fontweight="bold", color=primary, pad=12)

        path = save_path or str(engine.output_dir / f"bridge_{engine.style_id}.png")
        plt.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close()
        engine.generated.append(path)
        return path
    except Exception as e:
        logger.warning(f"Bridge chart failed: {e}")
        return None
