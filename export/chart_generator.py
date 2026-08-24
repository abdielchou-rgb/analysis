"""
1号分析师 V30 — 图表生成器 (Chart Generator)

用 matplotlib 生成投行风格分析图表，保存为 300 DPI PNG 文件。

图表类型:
  1. bar       — 多组数据柱状对比（如各年营收对比）
  2. line      — 时间趋势（如毛利率趋势）
  3. combo     — 柱状+折线双轴组合（如营收柱状+ROE折线）
  4. waterfall — 估值拆解/收入桥分解瀑布图
  5. radar     — 竞争格局/管理层评估雷达图（6维度）
  6. heatmap   — 敏感性分析矩阵（5x5）

配色方案（投行风格）:
  - 主色:  深海蓝 #003366
  - 正色:  森林绿 #2E7D32
  - 负色:  深红色 #C62828
  - 中性色: 灰色  #666666
  - 辅助蓝: #4A90D9

输出: outputs/charts/{stock_code}_chart_{id}.png (300 DPI)
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger("v30.chart")


# Chinese font setup
import os as _os

import matplotlib.font_manager as _fm

_yahei_path = _os.path.join("C:\\Windows\\Fonts", "msyh.ttc")
if _os.path.exists(_yahei_path):
    _fm.fontManager.addfont(_yahei_path)
    import matplotlib.pyplot as _plt

    _plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    _plt.rcParams["axes.unicode_minus"] = False

COLOR_DARK_BLUE = "#003366"
COLOR_BLUE = "#4A90D9"
COLOR_GREEN = "#2E7D32"
COLOR_RED = "#C62828"
COLOR_GRAY = "#666666"
COLOR_LIGHT_GRAY = "#BDBDBD"
COLOR_BG = "#F5F7FA"
COLOR_PALETTE = ["#003366", "#4A90D9", "#6BA3E0", "#2E7D32", "#66BB6A", "#FF8F00"]

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Noto Sans CJK JP", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.15,
    }
)


class ChartGenerator:
    def __init__(self, output_dir: str = "outputs/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._chart_counter: dict[str, int] = {}

    def _next_id(self, prefix: str = "chart") -> str:
        self._chart_counter[prefix] = self._chart_counter.get(prefix, 0) + 1
        return f"{prefix}_{self._chart_counter[prefix]:02d}"

    def _save(self, stock_code: str, chart_id: str) -> str:
        filename = re.sub(r"[^\w\-]", "_", f"{stock_code}_{chart_id}.png")
        path = str(self.output_dir / filename)
        plt.savefig(path, dpi=300, bbox_inches="tight", facecolor=COLOR_BG)
        plt.close()
        logger.info(f"  图表已保存: {path}")
        return path

    def _setup_style(self, ax, title: str, xlabel: str = "", ylabel: str = ""):
        ax.set_title(title, fontsize=14, fontweight="bold", color=COLOR_DARK_BLUE, pad=15)
        ax.set_xlabel(xlabel or "", fontsize=11, color=COLOR_GRAY)
        ax.set_ylabel(ylabel or "", fontsize=11, color=COLOR_GRAY)
        ax.set_facecolor("white")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(COLOR_LIGHT_GRAY)
        ax.spines["bottom"].set_color(COLOR_LIGHT_GRAY)
        ax.tick_params(colors=COLOR_GRAY, labelsize=10)
        ax.grid(axis="y", alpha=0.3, color=COLOR_LIGHT_GRAY, linestyle="--")

    # ═══════════════════════════════════
    # 1. 柱状图
    # ═══════════════════════════════════

    def bar_chart(
        self,
        data: list[list[float]],
        labels: list[str],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        group_labels: list[str] | None = None,
        stock_code: str = "unknown",
    ) -> str:
        fig, ax = plt.subplots(figsize=(10, 6), facecolor=COLOR_BG)
        self._setup_style(ax, title, xlabel, ylabel)

        n_groups = len(data)
        n_items = len(labels)
        bar_width = 0.7 / max(n_groups, 1)
        x = np.arange(n_items)

        if group_labels is None:
            group_labels = [f"系列{i + 1}" for i in range(n_groups)]

        for i, group_data in enumerate(data):
            offset = (i - (n_groups - 1) / 2) * bar_width
            color = COLOR_PALETTE[i % len(COLOR_PALETTE)]
            bars = ax.bar(
                x + offset,
                group_data,
                bar_width * 0.9,
                label=group_labels[i],
                color=color,
                edgecolor="white",
                linewidth=0.5,
            )
            for bar, val in zip(bars, group_data):
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height(),
                        f"{val:.1f}" if abs(val) < 1000 else f"{val:.0f}",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                        color=COLOR_GRAY,
                    )

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10)
        ax.legend(fontsize=10, loc="upper left", frameon=True, facecolor="white")
        return self._save(stock_code, self._next_id("bar"))

    # ═══════════════════════════════════
    # 2. 折线图
    # ═══════════════════════════════════

    def line_chart(
        self,
        data_series: list[dict],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        stock_code: str = "unknown",
    ) -> str:
        fig, ax = plt.subplots(figsize=(10, 6), facecolor=COLOR_BG)
        self._setup_style(ax, title, xlabel, ylabel)

        markers = ["o", "s", "D", "^", "v", "<", ">"]
        for i, series in enumerate(data_series):
            color = COLOR_PALETTE[i % len(COLOR_PALETTE)]
            marker = markers[i % len(markers)]
            ax.plot(
                series["x"],
                series["y"],
                label=series["label"],
                color=color,
                linewidth=2,
                marker=marker,
                markersize=6,
                markerfacecolor=color,
                markeredgecolor="white",
                markeredgewidth=0.5,
            )
            if series["y"]:
                last_y, last_x = series["y"][-1], series["x"][-1]
                if last_y is not None:
                    ax.annotate(
                        f"{last_y:.1f}",
                        xy=(last_x, last_y),
                        xytext=(8, 0),
                        textcoords="offset points",
                        fontsize=9,
                        color=color,
                        fontweight="bold",
                    )

        ax.legend(fontsize=10, loc="best", frameon=True, facecolor="white")
        return self._save(stock_code, self._next_id("line"))

    # ═══════════════════════════════════
    # 3. 组合图（柱状+折线双轴）
    # ═══════════════════════════════════

    def combo_chart(
        self,
        bars: dict,
        line: dict,
        title: str = "",
        stock_code: str = "unknown",
    ) -> str:
        fig, ax1 = plt.subplots(figsize=(10, 6), facecolor=COLOR_BG)

        bar_color = bars.get("color", COLOR_DARK_BLUE)
        x = np.arange(len(bars["labels"]))
        ax1.bar(
            x,
            bars["values"],
            width=0.5,
            color=bar_color,
            alpha=0.85,
            edgecolor="white",
            linewidth=0.5,
            label=bars.get("label", ""),
        )
        ax1.set_xlabel(bars.get("xlabel", ""), fontsize=11, color=COLOR_GRAY)
        ax1.set_ylabel(bars.get("ylabel", "营收(亿元)"), fontsize=11, color=bar_color)
        ax1.tick_params(axis="y", labelcolor=bar_color)
        ax1.set_xticks(x)
        ax1.set_xticklabels(bars["labels"], fontsize=10)
        ax1.set_facecolor("white")

        line_color = line.get("color", COLOR_GREEN)
        ax2 = ax1.twinx()
        ax2.plot(
            x,
            line["values"],
            color=line_color,
            linewidth=2.5,
            marker="o",
            markersize=7,
            markerfacecolor=line_color,
            markeredgecolor="white",
            markeredgewidth=0.5,
            label=line.get("label", ""),
            zorder=5,
        )
        ax2.set_ylabel(line.get("ylabel", "ROE(%)"), fontsize=11, color=line_color)
        ax2.tick_params(axis="y", labelcolor=line_color)

        for xi, val in zip(x, line["values"]):
            if val is not None:
                ax2.annotate(
                    f"{val:.1f}",
                    xy=(xi, val),
                    xytext=(0, 10),
                    textcoords="offset points",
                    ha="center",
                    fontsize=9,
                    color=line_color,
                    fontweight="bold",
                )

        ax1.set_title(title, fontsize=14, fontweight="bold", color=COLOR_DARK_BLUE, pad=15)
        ax1.spines["top"].set_visible(False)
        ax2.spines["top"].set_visible(False)

        h1, l1 = ax1.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax1.legend(h1 + h2, l1 + l2, fontsize=10, loc="upper left", frameon=True, facecolor="white")

        fig.tight_layout()
        return self._save(stock_code, self._next_id("combo"))

    # ═══════════════════════════════════
    # 4. 瀑布图
    # ═══════════════════════════════════

    def waterfall(
        self,
        categories: list[str],
        values: list[float],
        title: str = "",
        stock_code: str = "unknown",
    ) -> str:
        fig, ax = plt.subplots(figsize=(12, 6), facecolor=COLOR_BG)
        self._setup_style(ax, title, "", "亿元")

        n = len(categories)
        if n != len(values):
            raise ValueError(f"categories({n}) 和 values({len(values)}) 长度不一致")

        bottoms = [0.0] * n
        running = values[0]
        for i in range(1, n):
            if values[i] >= 0:
                bottoms[i] = running
                running += values[i]
            else:
                bottoms[i] = running + values[i]
                running += values[i]

        colors = []
        for i in range(n):
            if i == 0 or i == n - 1:
                colors.append(COLOR_DARK_BLUE)
            elif values[i] >= 0:
                colors.append(COLOR_GREEN)
            else:
                colors.append(COLOR_RED)

        bar_vals = [abs(v) if 0 < i < n - 1 else v for i, v in enumerate(values)]
        ax.bar(range(n), bar_vals, bottom=bottoms, color=colors, edgecolor="white", linewidth=0.8, width=0.6)

        for i in range(n - 1):
            curr_top = bottoms[i] + (values[i] if i == 0 or i == n - 1 else abs(values[i]))
            ax.plot([i + 0.3, i + 0.7], [curr_top, curr_top], color=COLOR_LIGHT_GRAY, linewidth=1, linestyle="--")

        for i, (cat, val) in enumerate(zip(categories, values)):
            label = f"{val:.1f}" if i == 0 or i == n - 1 else f"{val:+.1f}"
            y_pos = (val if i == 0 or i == n - 1 else abs(val)) + (bottoms[i] if i > 0 else 0) + 0.5
            clr = COLOR_DARK_BLUE if i == 0 or i == n - 1 else (COLOR_GREEN if val >= 0 else COLOR_RED)
            ax.text(i, y_pos, label, ha="center", va="bottom", fontsize=10, fontweight="bold", color=clr)

        ax.set_xticks(range(n))
        ax.set_xticklabels(categories, fontsize=9, rotation=15, ha="right")
        return self._save(stock_code, self._next_id("waterfall"))

    # ═══════════════════════════════════
    # 5. 雷达图
    # ═══════════════════════════════════

    def radar(
        self,
        categories: list[str],
        values_matrix: list[list[float]],
        labels: list[str],
        title: str = "",
        stock_code: str = "unknown",
    ) -> str:
        n_dim = len(categories)
        if n_dim < 3:
            raise ValueError("雷达图至少需要3个维度")

        angles = np.linspace(0, 2 * np.pi, n_dim, endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection": "polar"}, facecolor=COLOR_BG)

        for i, values in enumerate(values_matrix):
            values_closed = values + values[:1]
            color = COLOR_PALETTE[i % len(COLOR_PALETTE)]
            ax.plot(angles, values_closed, "o-", linewidth=2, label=labels[i], color=color, markersize=6)
            ax.fill(angles, values_closed, alpha=0.08, color=color)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=11, color=COLOR_DARK_BLUE)
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8, color=COLOR_GRAY)
        ax.set_title(title, fontsize=14, fontweight="bold", color=COLOR_DARK_BLUE, pad=25, va="bottom")
        ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=10, frameon=True, facecolor="white")
        ax.set_facecolor("white")
        ax.grid(alpha=0.3, color=COLOR_LIGHT_GRAY)
        fig.tight_layout()
        return self._save(stock_code, self._next_id("radar"))

    # ═══════════════════════════════════
    # 6. 热力图
    # ═══════════════════════════════════

    def heatmap(
        self,
        matrix: list[list[float]],
        xlabels: list[str],
        ylabels: list[str],
        title: str = "",
        stock_code: str = "unknown",
        value_format: str = "{:.1f}",
        cmap_name: str = "RdYlGn",
    ) -> str:
        matrix_np = np.array(matrix)
        n_rows, n_cols = matrix_np.shape

        fig, ax = plt.subplots(figsize=(10, 8), facecolor=COLOR_BG)

        vmax = max(abs(matrix_np.min()), abs(matrix_np.max()))
        vmin = -vmax if vmax > 0 else 0

        im = ax.imshow(matrix_np, cmap=cmap_name, aspect="auto", vmin=vmin, vmax=vmax)

        for i in range(n_rows):
            for j in range(n_cols):
                val = matrix_np[i, j]
                text_color = "white" if abs(val) > vmax * 0.6 else COLOR_DARK_BLUE
                ax.text(
                    j,
                    i,
                    value_format.format(val),
                    ha="center",
                    va="center",
                    fontsize=11,
                    fontweight="bold",
                    color=text_color,
                )

        ax.set_xticks(range(n_cols))
        ax.set_yticks(range(n_rows))
        ax.set_xticklabels(xlabels, fontsize=10, rotation=0)
        ax.set_yticklabels(ylabels, fontsize=10)
        ax.set_title(title, fontsize=14, fontweight="bold", color=COLOR_DARK_BLUE, pad=15)

        cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        cbar.ax.tick_params(labelsize=9, colors=COLOR_GRAY)

        ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=2)
        ax.tick_params(which="minor", bottom=False, left=False)

        fig.tight_layout()
        return self._save(stock_code, self._next_id("heatmap"))

    # ═══════════════════════════════════
    # 7. 投行级注解: 在任意图上加标注框
    # ═══════════════════════════════════

    def add_annotation_box(self, ax, text: str, xy, fontsize: int = 10, color: str = None, box_alpha: float = 0.15):
        """在指定位置添加投行风格的注解框。"""
        if color is None:
            color = COLOR_DARK_BLUE
        ax.annotate(
            text,
            xy=xy,
            xytext=(12, 0),
            textcoords="offset points",
            fontsize=fontsize,
            color=color,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=box_alpha, edgecolor=color, linewidth=0.5),
            arrowprops=dict(arrowstyle="->", color=color, lw=1.0),
        )

    def add_horizontal_benchmark(self, ax, y: float, label: str, color: str = None, linestyle: str = "--"):
        """添加水平基准线（投行常用，如行业均值、目标价等）。"""
        if color is None:
            color = COLOR_RED
        ax.axhline(y=y, color=color, linestyle=linestyle, linewidth=1.5, alpha=0.8)
        ax.text(ax.get_xlim()[1], y, " " + label, va="center", fontsize=9, color=color, fontweight="bold")

    def add_valuation_range(self, ax, x, low: float, high: float, label: str, color: str = None):
        """添加估值区间标注（如 PE 区间 15x-25x）。"""
        if color is None:
            color = COLOR_BLUE
        ax.annotate("", xy=(x, low), xytext=(x, high), arrowprops=dict(arrowstyle="<->", color=color, lw=2.0))
        mid = (low + high) / 2
        ax.text(
            x,
            mid,
            " " + label,
            ha="center",
            va="center",
            fontsize=9,
            color=color,
            fontweight="bold",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

    # ═══════════════════════════════════
    # 8. 分组柱状图（投行级多公司对比）
    # ═══════════════════════════════════

    def group_bar(
        self,
        categories: list[str],
        series: list[dict],
        title: str = "",
        ylabel: str = "",
        stock_code: str = "unknown",
        show_legend: bool = True,
    ) -> str:
        """多公司分组对比柱状图。"""
        fig, ax = plt.subplots(figsize=(12, 6), facecolor=COLOR_BG)
        self._setup_style(ax, title, "", ylabel)

        n_cats = len(categories)
        n_series = len(series)
        bar_width = 0.7 / max(n_series, 1)
        x = np.arange(n_cats)

        for i, s in enumerate(series):
            offset = (i - (n_series - 1) / 2) * bar_width
            color = COLOR_PALETTE[i % len(COLOR_PALETTE)]
            vals = [v if v is not None else 0 for v in s["values"]]
            bars = ax.bar(
                x + offset,
                vals,
                bar_width * 0.9,
                label=s.get("label", ""),
                color=color,
                edgecolor="white",
                linewidth=0.5,
            )

        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=10, rotation=15, ha="right")
        if show_legend:
            ax.legend(fontsize=9, loc="upper right", frameon=True, facecolor="white")
        return self._save(stock_code, self._next_id("group_bar"))


def generate_financial_charts(
    computed, stock_code: str = "unknown", output_dir: str = "outputs/charts"
) -> dict[str, str]:
    cg = ChartGenerator(output_dir)
    charts = {}

    fs = computed.financial_summary
    years = [str(y) for y in fs.years]
    if not years:
        logger.warning("无财务年份数据，跳过图表生成")
        return charts

    revenues = fs.items.get("营收(亿元)", {})
    rev_values = [revenues.get(y) for y in years]
    rev_clean = [v if v is not None else 0 for v in rev_values]

    margins = fs.items.get("毛利率(%)", {})
    net_margins = fs.items.get("净利率(%)", {})
    roes = fs.items.get("ROE(%)", {})
    rev_growth = fs.items.get("营收增速(%)", {})
    profit_growth = fs.items.get("净利增速(%)", {})

    # 1. 营收柱状图
    if any(v is not None for v in rev_values):
        charts["revenue_trend"] = cg.bar_chart(
            data=[rev_clean],
            labels=years,
            title=f"{computed.company} 营收趋势",
            xlabel="年份",
            ylabel="营收(亿元)",
            group_labels=["营收"],
            stock_code=stock_code,
        )

    # 2. 利润率趋势
    margin_series = []
    margin_raw = [margins.get(y) for y in years]
    net_margin_raw = [net_margins.get(y) for y in years]
    if any(v is not None for v in margin_raw):
        margin_series.append({"label": "毛利率", "x": years, "y": [v if v is not None else 0 for v in margin_raw]})
    if any(v is not None for v in net_margin_raw):
        margin_series.append({"label": "净利率", "x": years, "y": [v if v is not None else 0 for v in net_margin_raw]})
    if margin_series:
        charts["margin_trend"] = cg.line_chart(
            data_series=margin_series,
            title=f"{computed.company} 利润率趋势(%)",
            xlabel="年份",
            ylabel="%",
            stock_code=stock_code,
        )

    # 3. ROE 趋势
    roe_raw = [roes.get(y) for y in years]
    if any(v is not None for v in roe_raw):
        charts["roe_trend"] = cg.line_chart(
            data_series=[{"label": "ROE", "x": years, "y": [v if v is not None else 0 for v in roe_raw]}],
            title=f"{computed.company} ROE 趋势(%)",
            xlabel="年份",
            ylabel="%",
            stock_code=stock_code,
        )

    # 4. 营收 + ROE 组合图
    if any(v is not None for v in rev_values) and any(v is not None for v in roe_raw):
        charts["revenue_roe_combo"] = cg.combo_chart(
            bars={
                "labels": years,
                "values": rev_clean,
                "label": "营收(亿元)",
                "xlabel": "年份",
                "ylabel": "营收(亿元)",
            },
            line={
                "labels": years,
                "values": [v if v is not None else 0 for v in roe_raw],
                "label": "ROE(%)",
                "ylabel": "ROE(%)",
            },
            title=f"{computed.company} 营收与ROE组合分析",
            stock_code=stock_code,
        )

    # 5. 增长趋势
    growth_series = []
    rg_raw = [rev_growth.get(y) for y in years]
    pg_raw = [profit_growth.get(y) for y in years]
    if any(v is not None for v in rg_raw):
        growth_series.append({"label": "营收增速", "x": years, "y": [v if v is not None else 0 for v in rg_raw]})
    if any(v is not None for v in pg_raw):
        growth_series.append({"label": "净利增速", "x": years, "y": [v if v is not None else 0 for v in pg_raw]})
    if growth_series:
        charts["growth_trend"] = cg.line_chart(
            data_series=growth_series,
            title=f"{computed.company} 增长趋势(%)",
            xlabel="年份",
            ylabel="同比增速(%)",
            stock_code=stock_code,
        )

    # 6. 竞争对标雷达图（当有 comparable_result 数据时）
    if computed.comparable_result and isinstance(computed.comparable_result, dict):
        comp_data = computed.comparable_result
        peer_names = comp_data.get("peer_names", [])
        metrics_org = comp_data.get("metrics", {})
        if len(peer_names) >= 2:
            cat_map = {
                "gross_margin": "毛利率",
                "net_margin": "净利率",
                "roe": "ROE",
                "revenue_yoy": "营收增速",
                "liability_to_asset": "负债率",
            }
            cats_radar = []
            values_matrix = []
            labels = [computed.company] + peer_names[:3]  # 限制3家对比避免过于拥挤
            for metric_key, cat_label in cat_map.items():
                metric_data = metrics_org.get(metric_key, {})
                vals_for_dim = []
                for lbl in labels:
                    v = metric_data.get(lbl)
                    vals_for_dim.append(float(v) if v is not None else 0)
                cats_radar.append(cat_label)
                if len(values_matrix) == 0:
                    for _ in labels:
                        values_matrix.append([])
                for i, vi in enumerate(vals_for_dim):
                    if len(values_matrix) <= i:
                        values_matrix.append([])
                    # Normalize to 0-100 scale
                    norm_val = min(max(vi, 0), 100)
                    values_matrix[i].append(norm_val)

            if len(cats_radar) >= 3 and len(values_matrix) == len(labels):
                charts["radar_benchmark"] = cg.radar(
                    categories=cats_radar,
                    values_matrix=values_matrix,
                    labels=labels,
                    title=f"{computed.company} 竞争对标雷达图",
                    stock_code=stock_code,
                )

    # 7. 利润瀑布图（收入桥分解）
    rb = computed.revenue_bridge
    if rb:
        drivers = rb.drivers
        if drivers and rb.total_revenue_change_abs is not None:
            cats = ["上期营收"]
            vals = [rb.total_revenue_change_abs]
            # Simplified: just show total as waterfall
            for d in drivers[:3]:
                segment = d.get("segment", d.get("period", ""))[:10]
                yoy = d.get("yoy_pct", 0)
                if yoy:
                    cats.append(segment)
                    vals.append(yoy * 1.5)  # approximate contribution
            cats.append("本期营收")
            vals.append(0)  # placeholder for total
            if len(vals) >= 4:
                charts["revenue_waterfall"] = cg.waterfall(
                    categories=cats,
                    values=vals,
                    title=f"{computed.company} 收入桥瀑布图",
                    stock_code=stock_code,
                )

    return charts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("=" * 60)
    print("1号分析师 V30 — 图表生成器 (Chart Generator)")
    print("=" * 60)
    print("用法: python tools/chart_generator.py <stock_code>")
    if len(sys.argv) < 2:
        print("请指定股票代码")
        sys.exit(0)
    print("此模块通常由 orchestrator.run 调用生成实际图表演示")
