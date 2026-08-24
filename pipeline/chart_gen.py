"""pipeline/chart_gen.py — Standalone chart generator (no V30 dependency)"""
import sys, re, logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = _ROOT / "outputs" / "charts"
logger = logging.getLogger("2hao.chart_gen")

# Global style
COLORS = {"dark_blue":"#003366","blue":"#4A90D9","green":"#2E7D32","red":"#C62828",
          "gray":"#666666","light_gray":"#BDBDBD","bg":"#F5F7FA"}
PALETTE = ["#003366","#4A90D9","#6BA3E0","#2E7D32","#66BB6A","#FF8F00"]

class ChartGen:
    """纯matplotlib图表生成器（零外部依赖）"""

    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _setup(self, ax, title, xl="", yl=""):
        ax.set_title(title, fontsize=13, fontweight="bold", color=COLORS["dark_blue"], pad=12)
        ax.set_xlabel(xl or "", fontsize=10, color=COLORS["gray"])
        ax.set_ylabel(yl or "", fontsize=10, color=COLORS["gray"])
        ax.set_facecolor("white")
        for s in ["top","right"]: ax.spines[s].set_visible(False)
        ax.spines["left"].set_color(COLORS["light_gray"])
        ax.spines["bottom"].set_color(COLORS["light_gray"])
        ax.tick_params(colors=COLORS["gray"], labelsize=9)
        ax.grid(axis="y", alpha=0.3, color=COLORS["light_gray"], linestyle="--")

    def _save(self, name, asset):
        fname = re.sub(r"[^\w\-]", "_", f"{asset}_{name}.png") if asset else f"{name}.png"
        path = str(self.output_dir / fname)
        try:
            plt.savefig(path, dpi=300, bbox_inches="tight", facecolor=COLORS["bg"])
            plt.close()
            return path
        except Exception: return ""

    def bar(self, values, labels, title="", xl="", yl="", asset=""):
        import numpy as np
        fig, ax = plt.subplots(figsize=(10,5), facecolor=COLORS["bg"])
        self._setup(ax, title, xl, yl)
        x = np.arange(len(labels))
        bars = ax.bar(x, values, 0.6, color=COLORS["blue"], edgecolor="white", linewidth=0.5)
        for bar, val in zip(bars, values):
            if val: ax.text(bar.get_x()+bar.get_width()/2, bar.get_height(), f"{val:.1f}",
                           ha="center", va="bottom", fontsize=8, color=COLORS["gray"])
        ax.set_xticks(x); ax.set_xticklabels(labels)
        return self._save("bar", asset)

    def line(self, series, title="", xl="", yl="", asset=""):
        fig, ax = plt.subplots(figsize=(10,5), facecolor=COLORS["bg"])
        self._setup(ax, title, xl, yl)
        for i, s in enumerate(series):
            ax.plot(s["x"], s["y"], "-o", color=PALETTE[i%len(PALETTE)],
                    label=s["label"], linewidth=2, markersize=5)
        ax.legend(fontsize=9, loc="best")
        return self._save("line", asset)

    def combo(self, bars, line_data, title="", asset=""):
        import numpy as np
        fig, ax1 = plt.subplots(figsize=(10,5), facecolor=COLORS["bg"])
        self._setup(ax1, title, bars.get("xl",""), bars.get("yl",""))
        x = np.arange(len(bars["labels"]))
        bars_plot = ax1.bar(x, bars["values"], 0.5, color=COLORS["blue"], alpha=0.8, label=bars["label"])
        ax2 = ax1.twinx()
        ax2.plot(x, line_data["values"], "-o", color=COLORS["red"], linewidth=2, markersize=5, label=line_data["label"])
        ax2.set_ylabel(line_data.get("yl",""), fontsize=10, color=COLORS["gray"])
        ax2.tick_params(colors=COLORS["gray"], labelsize=9)
        ax2.spines["top"].set_visible(False)
        ax1.set_xticks(x); ax1.set_xticklabels(bars["labels"])
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1+lines2, labels1+labels2, fontsize=9, loc="upper left")
        return self._save("combo", asset)

    def heatmap(self, data, xlabels, ylabels, title="", asset=""):
        import numpy as np
        fig, ax = plt.subplots(figsize=(8,6), facecolor=COLORS["bg"])
        self._setup(ax, title)
        im = ax.imshow(np.array(data), cmap="RdYlGn_r", aspect="auto")
        cbar = fig.colorbar(im, ax=ax, shrink=0.8)
        ax.set_xticks(np.arange(len(xlabels))); ax.set_xticklabels(xlabels)
        ax.set_yticks(np.arange(len(ylabels))); ax.set_yticklabels(ylabels)
        for i in range(len(ylabels)):
            for j in range(len(xlabels)):
                ax.text(j, i, f"{data[i][j]:.1f}", ha="center", va="center", fontsize=8, color="black")
        ax.set_xlabel("终端增长率", fontsize=10, color=COLORS["gray"])
        ax.set_ylabel("WACC", fontsize=10, color=COLORS["gray"])
        return self._save("heatmap", asset)

    def waterfall(self, categories, values, title="", asset=""):
        import numpy as np
        fig, ax = plt.subplots(figsize=(10,5), facecolor=COLORS["bg"])
        self._setup(ax, title)
        n = len(categories)
        x = np.arange(n)
        running = 0
        for i in range(n-1):
            v = max(values[i], 0) if i % 2 == 0 else abs(values[i])
            color = COLORS["green"] if v >= 0 else COLORS["red"]
            ax.bar(i, v, 0.5, color=color, alpha=0.8)
            ax.text(i, v/2, f"{v:.1f}", ha="center", va="center", fontsize=9, color="white", fontweight="bold")
        total = sum(abs(v) for v in values[:-1])
        ax.bar(n-1, total, 0.5, color=COLORS["dark_blue"], alpha=0.9)
        ax.text(n-1, total/2, f"{total:.1f}", ha="center", va="center", fontsize=9, color="white", fontweight="bold")
        ax.set_xticks(x); ax.set_xticklabels(categories, rotation=30, ha="right")
        return self._save("waterfall", asset)


def generate_all_charts(data: dict, asset: str = "") -> dict:
    """Generate all standard charts from data dict. Returns {chart_id: filepath}"""
    cg = ChartGen()
    charts = {}
    cd = data.get("chart_data", {})

    # Bar: Revenue trend
    rev = cd.get("fig_revenue_trend", {})
    if rev and isinstance(rev, dict):
        yrs, vals = [], []
        for yr in sorted(rev.keys()):
            try:
                y = int(yr) if yr.isdigit() else yr
                v = float(rev[yr].get("revenue", rev[yr]) if isinstance(rev[yr], dict) else rev[yr]) if rev[yr] else 0
                yrs.append(str(y)); vals.append(v)
            except Exception:
                pass  # Layer 5: bare except replaced with Exception
        if len(vals) >= 3:
            p = cg.bar(vals, yrs, title=f"{asset} 收入趋势(亿元)", xl="年份", yl="亿元", asset=asset)
            if p: charts["revenue_trend"] = p

    # Line: Margin trend
    margin = cd.get("fig_profitability", {})
    if margin and isinstance(margin, dict):
        yrs, vals = [], []
        for yr in sorted(margin.keys()):
            try:
                y = int(yr) if yr.isdigit() else yr
                v = float(margin[yr].get("gross_margin", margin[yr]) if isinstance(margin[yr], dict) else margin[yr]) if margin[yr] else 0
                yrs.append(str(y)); vals.append(v)
            except Exception:
                pass  # Layer 5: bare except replaced with Exception
        if len(vals) >= 3:
            p = cg.line([{"label":"毛利率%","x":yrs,"y":vals}], title=f"{asset} 毛利率趋势", xl="年份", yl="%", asset=asset)
            if p: charts["margin_trend"] = p

    # Heatmap: DCF sensitivity
    val = cd.get("fig_valuation", {})
    fcf = float(val.get("free_cash_flow", 0)) if val.get("free_cash_flow") else 0
    if fcf > 0:
        grid = []
        for w in [8.0,9.0,10.0,11.0,12.0]:
            row = [round(fcf*(1+g/100)/(w/100-g/100),1) if w > g else 0 for g in [2.0,2.5,3.0,3.5,4.0]]
            grid.append(row)
        p = cg.heatmap(grid, [f"{g}%" for g in [2.0,2.5,3.0,3.5,4.0]], [f"{w}%" for w in [8.0,9.0,10.0,11.0,12.0]],
                       title=f"{asset} DCF灵敏度矩阵(WACCx终端增长率)", asset=asset)
        if p: charts["dcf_sensitivity"] = p

    return charts

