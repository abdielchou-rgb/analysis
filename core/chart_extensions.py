"""V53+ Chart Extensions - Production quality.
Tornado, Box, Stacked Bar, Radar charts with institutional styling.

All functions accept a ChartEngine instance and use its style dict.
"""

import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger("v53.chart_extensions")


def tornado_chart(
    engine,
    base_value: float,
    upside: float,
    downside: float,
    drivers: list[dict],
    title: str = "Valuation Sensitivity",
    save_path: str = "",
    data_source: str = "",
    figure_num: int = None,
) -> str | None:
    """Tornado chart for sensitivity analysis.

    drivers: [{"name": "Revenue Growth", "high": 55.0, "low": 35.0}, ...]
    Shows which drivers have the most impact on valuation.
    """
    if not drivers:
        return None
    try:
        sorted_drivers = sorted(drivers, key=lambda d: abs(d.get("high", 0) - d.get("low", 0)), reverse=True)
        fig, ax = plt.subplots(figsize=(10, max(4, len(sorted_drivers) * 0.6)))

        names = [d["name"] for d in sorted_drivers]
        lows = [d.get("low", base_value) - base_value for d in sorted_drivers]
        highs = [d.get("high", base_value) - base_value for d in sorted_drivers]
        y_pos = range(len(names))

        # Use institution palette
        primary = engine.style.get("primary", "#003366")
        accent = engine.style.get("accent", "#C41E3A")
        positive_color = engine.style.get("positive", accent)
        negative_color = engine.style.get("negative", primary)

        # Downside (left) - negative color
        bars_low = ax.barh(y_pos, lows, left=base_value, color=negative_color, alpha=0.7, height=0.5, label="Downside")
        # Upside (right) - positive color
        bars_high = ax.barh(y_pos, highs, left=base_value, color=positive_color, alpha=0.7, height=0.5, label="Upside")

        # Base value line
        ax.axvline(x=base_value, color="black", linewidth=1.5, linestyle="-", alpha=0.8)
        ax.text(
            base_value, len(names), f"Base:{base_value:.0f}", ha="center", va="bottom", fontsize=9, fontweight="bold"
        )

        # Value labels
        for i, (low, high) in enumerate(zip(lows, highs)):
            if low != 0:
                ax.text(
                    base_value + low - abs(low) * 0.15,
                    i,
                    f"{base_value + low:.0f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white",
                    fontweight="bold",
                )
            if high != 0:
                ax.text(
                    base_value + high - abs(high) * 0.15,
                    i,
                    f"{base_value + high:.0f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white",
                    fontweight="bold",
                )

        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(names, fontsize=9)
        ax.legend(loc="lower right", fontsize=9)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}"))

        # Apply institutional styling
        try:
            from utils.chart_config import apply_institution_style

            apply_institution_style(ax, engine.style, title, figure_num, data_source)
        except Exception:
            ax.set_title(title, fontsize=13, fontweight="bold", color=primary, pad=12)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        path = save_path or str(engine.output_dir / f"tornado_{engine.style_id}.png")
        plt.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close()
        engine.generated.append(path)
        return path
    except Exception as e:
        logger.warning(f"Tornado chart failed: {e}")
        return None


def box_chart(
    engine,
    data: dict[str, list[float]],
    title: str = "Industry Distribution Comparison",
    save_path: str = "",
    data_source: str = "",
    figure_num: int = None,
) -> str | None:
    """Box plot for assumption distribution visualization.

    data: {"Revenue CAGR": [0.05, 0.08, ...], "Gross Margin": [0.20, ...]}
    """
    if not data or len(data) < 2:
        return None
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        labels = list(data.keys())
        values = [data[k] for k in labels]

        palette = engine.style.get("palette", ["#003366", "#C41E3A", "#E8C84C", "#4CB8E8", "#666666"])
        bp = ax.boxplot(
            values,
            patch_artist=True,
            widths=0.5,
            medianprops={"color": "white", "linewidth": 2},
            whiskerprops={"linewidth": 1.5},
            capprops={"linewidth": 1.5},
        )

        for i, patch in enumerate(bp["boxes"]):
            patch.set_facecolor(palette[i % len(palette)])
            patch.set_alpha(0.75)

        # Jittered scatter overlay
        for i, vals in enumerate(values):
            jitter = np.random.normal(0, 0.04, size=len(vals))
            ax.scatter(
                np.ones(len(vals)) * (i + 1) + jitter, vals, alpha=0.4, s=20, color=palette[i % len(palette)], zorder=3
            )

        ax.set_xticklabels(labels, fontsize=9, rotation=15)
        ax.set_ylabel("Value", fontsize=10)

        try:
            from utils.chart_config import apply_institution_style

            apply_institution_style(ax, engine.style, title, figure_num, data_source)
        except Exception:
            ax.set_title(title, fontsize=13, fontweight="bold", color=engine.style.get("primary", "#003366"), pad=12)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        path = save_path or str(engine.output_dir / f"box_{engine.style_id}.png")
        plt.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close()
        engine.generated.append(path)
        return path
    except Exception as e:
        logger.warning(f"Box chart failed: {e}")
        return None


def stacked_bar_chart(
    engine,
    categories: list[str],
    series: dict[str, list[float]],
    title: str = "Scenario Comparison",
    save_path: str = "",
    data_source: str = "",
    figure_num: int = None,
) -> str | None:
    """Stacked bar for Conviction Matrix scenario comparison."""
    if not categories or not series:
        return None
    try:
        n_cats = len(categories)
        n_series = len(series)
        palette = engine.style.get("palette", ["#003366", "#C41E3A", "#E8C84C", "#4CB8E8", "#666666"])

        fig, axes = plt.subplots(1, n_series, figsize=(5 * n_series, 4))
        if n_series == 1:
            axes = [axes]

        for ax_idx, (s_name, s_values) in enumerate(series.items()):
            ax = axes[ax_idx]
            colors_list = [palette[i % len(palette)] for i in range(n_cats)]

            if "prob" in s_name.lower():
                wedges, texts, autotexts = ax.pie(
                    s_values,
                    labels=categories,
                    autopct="%1.0f%%",
                    colors=colors_list,
                    startangle=90,
                    textprops={"fontsize": 10},
                )
                ax.set_title(
                    f"{s_name} Distribution",
                    fontsize=12,
                    fontweight="bold",
                    color=engine.style.get("primary", "#003366"),
                )
            else:
                bars = ax.bar(categories, s_values, color=colors_list, width=0.5, edgecolor="white", linewidth=0.5)
                for bar, val in zip(bars, s_values):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(s_values) * 0.02,
                        f"{val:.1f}",
                        ha="center",
                        va="bottom",
                        fontsize=10,
                        fontweight="bold",
                    )
                ax.set_title(s_name, fontsize=12, fontweight="bold", color=engine.style.get("primary", "#003366"))
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)

        fig.suptitle(title, fontsize=14, fontweight="bold", y=1.02)
        path = save_path or str(engine.output_dir / f"stacked_bar_{engine.style_id}.png")
        plt.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close()
        engine.generated.append(path)
        return path
    except Exception as e:
        logger.warning(f"Stacked bar failed: {e}")
        return None


def radar_chart(
    engine,
    categories: list[str],
    values: list[float],
    title: str = "Multi-dimensional Score",
    save_path: str = "",
    data_source: str = "",
    figure_num: int = None,
) -> str | None:
    """Radar chart for multi-dimensional scoring."""
    if not categories or not values or len(categories) < 3:
        return None
    try:
        n = len(categories)
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
        angles += angles[:1]
        values_closed = values + values[:1]

        fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
        primary = engine.style.get("primary", "#003366")
        palette = engine.style.get("palette", [primary])

        ax.plot(angles, values_closed, "o-", linewidth=2, color=primary)
        ax.fill(angles, values_closed, alpha=0.25, color=primary)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=10)
        ax.set_ylim(0, max(values) * 1.2)

        try:
            from utils.chart_config import apply_institution_style

            apply_institution_style(ax, engine.style, title, figure_num, data_source)
        except Exception:
            ax.set_title(title, fontsize=13, fontweight="bold", pad=20)

        path = save_path or str(engine.output_dir / f"radar_{engine.style_id}.png")
        plt.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close()
        engine.generated.append(path)
        return path
    except Exception as e:
        logger.warning(f"Radar chart failed: {e}")
        return None
