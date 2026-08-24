"""
V53+ Production Chart Configuration
====================================
Production-grade institutional chart styling engine.
Loads 17-institution color templates from templates/*/colors.json
Fallback chain: templates/colors.json -> built-in 17 palettes -> STYLE_COLORS

Key upgrades from V53:
  1. Full 10-color palettes for all 17 institutions
  2. Institution-specific font, grid, annotation specs
  3. 200 DPI production rendering
  4. Automatic figure numbering with institution prefix
  5. Data source footnote integration
  6. Quality tiers: draft/review/final
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("v53.chart_config")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"
_FONTS_DIR = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"

_CANDIDATE_FONTS = [
    "simhei.ttf",
    "msyh.ttf",
    "msyhbd.ttf",
    "simsun.ttc",
    "simsunb.ttf",
    "dengxian.ttf",
]

# Institution palettes - 17 institutions with 10-color palettes + full specs
INSTITUTION_PALETTES: dict[str, dict] = {
    "cicc": {
        "primary": "#003366", "accent": "#C41E3A", "secondary": "#E8C84C",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E8E8E8",
        "positive": "#C41E3A", "negative": "#003366",
        "font_family": "SimSun",
        "font_family_en": "Times New Roman",
        "chart_border": False,
        "grid_style": {"alpha": 0.25, "linestyle": "--", "linewidth": 0.4},
        "spine_style": {"visible": True, "color": "#CCCCCC", "linewidth": 0.5},
        "data_label": {"fontsize": 7.5, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#999999"},
        "palette": ["#003366","#C41E3A","#E8C84C","#4CB8E8","#666666",
                    "#8B4513","#2E8B57","#9370DB","#CD853F","#708090"],
        "figure_prefix": "\u56fe",
        "figure_separator": "",
    },
    "gs": {
        "primary": "#051C2C", "accent": "#009688", "secondary": "#4CB8E8",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E5E5E5",
        "positive": "#009688", "negative": "#C41E3A",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Arial",
        "chart_border": False,
        "grid_style": {"alpha": 0.15, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#D0D0D0", "linewidth": 0.3},
        "data_label": {"fontsize": 8, "color": "#555555", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#051C2C","#009688","#4CB8E8","#B0D4E8","#63666A",
                    "#D4AF37","#8BB8D6","#C41E3A","#7F7F7F","#4DB8D8"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
    "ms": {
        "primary": "#000066", "accent": "#D4AF37", "secondary": "#4CB8E8",
        "bg": "#FAFCFF", "text": "#1A1A1A", "grid": "#E0E6ED",
        "positive": "#000066", "negative": "#D4AF37",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Arial",
        "chart_border": False,
        "grid_style": {"alpha": 0.2, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#C0C8D4", "linewidth": 0.4},
        "data_label": {"fontsize": 8, "color": "#333366", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888899"},
        "palette": ["#000066","#D4AF37","#4CB8E8","#B0D4E8","#666666",
                    "#8B4513","#2E8B57","#9370DB","#CD853F","#708090"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
    "mck": {
        "primary": "#003A70", "accent": "#00A3E0", "secondary": "#7ED321",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E0E8F0",
        "positive": "#00A3E0", "negative": "#003A70",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Calibri",
        "chart_border": False,
        "grid_style": {"alpha": 0.2, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#C8D0D8", "linewidth": 0.3},
        "data_label": {"fontsize": 8, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#003A70","#00A3E0","#7ED321","#4CB8E8","#333333",
                    "#B0D4E8","#D4AF37","#C41E3A","#666666","#999999"],
        "figure_prefix": "Exhibit ",
        "figure_separator": ": ",
    },
    "bcg": {
        "primary": "#000000", "accent": "#00684E", "secondary": "#7EC8E3",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E0E0E0",
        "positive": "#00684E", "negative": "#8B0000",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Calibri",
        "chart_border": False,
        "grid_style": {"alpha": 0.15, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#CCCCCC", "linewidth": 0.3},
        "data_label": {"fontsize": 8, "color": "#000000", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#666666"},
        "palette": ["#000000","#00684E","#7EC8E3","#00A3E0","#666666",
                    "#D4AF37","#8B0000","#4CB8E8","#999999","#333333"],
        "figure_prefix": "Exhibit ",
        "figure_separator": ": ",
    },
    "citic": {
        "primary": "#8B0000", "accent": "#D4A000", "secondary": "#333333",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E8E0E0",
        "positive": "#8B0000", "negative": "#333333",
        "font_family": "SimSun",
        "font_family_en": "Times New Roman",
        "chart_border": False,
        "grid_style": {"alpha": 0.25, "linestyle": "--", "linewidth": 0.4},
        "spine_style": {"visible": True, "color": "#CCBBBB", "linewidth": 0.5},
        "data_label": {"fontsize": 7.5, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#999999"},
        "palette": ["#8B0000","#D4A000","#333333","#4CB8E8","#666666",
                    "#B8860B","#2E8B57","#9370DB","#CD853F","#708090"],
        "figure_prefix": "\u56fe",
        "figure_separator": " ",
    },
    "csc": {
        "primary": "#003D7A", "accent": "#C8962E", "secondary": "#D4A843",
        "bg": "#FFFFFF", "text": "#333333", "grid": "#E8ECF0",
        "positive": "#003D7A", "negative": "#C8962E",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Arial",
        "chart_border": False,
        "grid_style": {"alpha": 0.2, "linestyle": "--", "linewidth": 0.35},
        "spine_style": {"visible": True, "color": "#C8D0D8", "linewidth": 0.4},
        "data_label": {"fontsize": 7.5, "color": "#444444", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#003D7A","#C8962E","#D4A843","#6B9BC4","#E0C87D",
                    "#8C8C8C","#2E5D8A","#B8860B","#4CB8E8","#666666"],
        "figure_prefix": "\u56fe",
        "figure_separator": " ",
    },
    "htsc": {
        "primary": "#003366", "accent": "#E8A020", "secondary": "#4CB8E8",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E8E8E8",
        "positive": "#003366", "negative": "#E8A020",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Arial",
        "chart_border": False,
        "grid_style": {"alpha": 0.2, "linestyle": "--", "linewidth": 0.35},
        "spine_style": {"visible": True, "color": "#CCCCCC", "linewidth": 0.4},
        "data_label": {"fontsize": 7.5, "color": "#444444", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#003366","#E8A020","#4CB8E8","#B0D4E8","#666666",
                    "#D4AF37","#2E8B57","#9370DB","#CD853F","#708090"],
        "figure_prefix": "\u56fe",
        "figure_separator": " ",
    },
    "jpm": {
        "primary": "#003366", "accent": "#4CB8E8", "secondary": "#B0D4E8",
        "bg": "#FAFCFF", "text": "#1A1A1A", "grid": "#E0E6ED",
        "positive": "#003366", "negative": "#C41E3A",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Arial",
        "chart_border": False,
        "grid_style": {"alpha": 0.2, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#C0C8D4", "linewidth": 0.4},
        "data_label": {"fontsize": 8, "color": "#333366", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#8888AA"},
        "palette": ["#003366","#4CB8E8","#B0D4E8","#666666","#999999",
                    "#D4AF37","#2E8B57","#9370DB","#C41E3A","#708090"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
    "citi": {
        "primary": "#003A70", "accent": "#00A3E0", "secondary": "#4CB8E8",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E0E8F0",
        "positive": "#00A3E0", "negative": "#C41E3A",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Arial",
        "chart_border": False,
        "grid_style": {"alpha": 0.2, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#C8D0D8", "linewidth": 0.3},
        "data_label": {"fontsize": 8, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#003A70","#00A3E0","#4CB8E8","#666666","#999999",
                    "#D4AF37","#2E8B57","#8B4513","#9370DB","#708090"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
    "bain": {
        "primary": "#003366", "accent": "#00A86B", "secondary": "#7ED321",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E0E8E8",
        "positive": "#00A86B", "negative": "#C41E3A",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Calibri",
        "chart_border": False,
        "grid_style": {"alpha": 0.2, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#C8D8D0", "linewidth": 0.3},
        "data_label": {"fontsize": 8, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#003366","#00A86B","#7ED321","#4CB8E8","#333333",
                    "#B0D4E8","#D4AF37","#C41E3A","#666666","#999999"],
        "figure_prefix": "Exhibit ",
        "figure_separator": ": ",
    },
    "deloitte": {
        "primary": "#003A70", "accent": "#00A3E0", "secondary": "#4CB8E8",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E0E8F0",
        "positive": "#00A3E0", "negative": "#C41E3A",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Calibri",
        "chart_border": True,
        "grid_style": {"alpha": 0.15, "linestyle": "--", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#CCCCCC", "linewidth": 0.4},
        "data_label": {"fontsize": 8, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#003A70","#00A3E0","#4CB8E8","#666666","#999999",
                    "#D4AF37","#2E8B57","#8B4513","#9370DB","#708090"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
    "ey": {
        "primary": "#1A1A1A", "accent": "#FFD100", "secondary": "#4CB8E8",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E8E8E0",
        "positive": "#1A1A1A", "negative": "#C41E3A",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Calibri",
        "chart_border": True,
        "grid_style": {"alpha": 0.2, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#D0D0D0", "linewidth": 0.4},
        "data_label": {"fontsize": 8, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#1A1A1A","#FFD100","#4CB8E8","#666666","#999999",
                    "#D4AF37","#2E8B57","#8B4513","#9370DB","#708090"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
    "kpmg": {
        "primary": "#003366", "accent": "#00A86B", "secondary": "#4CB8E8",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E0E8E8",
        "positive": "#00A86B", "negative": "#C41E3A",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Calibri",
        "chart_border": True,
        "grid_style": {"alpha": 0.2, "linestyle": "--", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#C8D8D0", "linewidth": 0.4},
        "data_label": {"fontsize": 8, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#003366","#00A86B","#4CB8E8","#B0D4E8","#666666",
                    "#D4AF37","#2E8B57","#8B4513","#9370DB","#708090"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
    "pwc": {
        "primary": "#FF6600", "accent": "#003A70", "secondary": "#4CB8E8",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#F0E8E0",
        "positive": "#FF6600", "negative": "#003A70",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Calibri",
        "chart_border": True,
        "grid_style": {"alpha": 0.2, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#D8D0C8", "linewidth": 0.4},
        "data_label": {"fontsize": 8, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#FF6600","#003A70","#4CB8E8","#666666","#999999",
                    "#D4AF37","#2E8B57","#8B4513","#9370DB","#708090"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
    "roland_berger": {
        "primary": "#003A70", "accent": "#00A3E0", "secondary": "#7EC8E3",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E0E8F0",
        "positive": "#00A3E0", "negative": "#C41E3A",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Calibri",
        "chart_border": False,
        "grid_style": {"alpha": 0.2, "linestyle": "--", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#C8D0D8", "linewidth": 0.4},
        "data_label": {"fontsize": 8, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#003A70","#00A3E0","#7EC8E3","#4CB8E8","#333333",
                    "#D4AF37","#2E8B57","#8B4513","#9370DB","#708090"],
        "figure_prefix": "Exhibit ",
        "figure_separator": ": ",
    },
    "accenture": {
        "primary": "#A100FF", "accent": "#000000", "secondary": "#4CB8E8",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#F0E8F8",
        "positive": "#A100FF", "negative": "#000000",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Calibri",
        "chart_border": False,
        "grid_style": {"alpha": 0.15, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#D8D0E0", "linewidth": 0.3},
        "data_label": {"fontsize": 8, "color": "#333333", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#A100FF","#000000","#4CB8E8","#666666","#999999",
                    "#D4AF37","#2E8B57","#8B4513","#9370DB","#708090"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
    "academic": {
        "primary": "#1A1A1A", "accent": "#2C5282", "secondary": "#666666",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E8E8E8",
        "positive": "#2C5282", "negative": "#8B0000",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Times New Roman",
        "chart_border": False,
        "grid_style": {"alpha": 0.2, "linestyle": "-", "linewidth": 0.3},
        "spine_style": {"visible": True, "color": "#CCCCCC", "linewidth": 0.4},
        "data_label": {"fontsize": 8, "color": "#444444", "format": "{:.2f}"},
        "annotation_style": {"fontsize": 7, "color": "#999999"},
        "palette": ["#1A1A1A","#2C5282","#666666","#4CB8E8","#999999",
                    "#8B4513","#2E8B57","#9370DB","#CD853F","#708090"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
    "standard": {
        "primary": "#003366", "accent": "#C41E3A", "secondary": "#E8C84C",
        "bg": "#FFFFFF", "text": "#1A1A1A", "grid": "#E8E8E8",
        "positive": "#003366", "negative": "#C41E3A",
        "font_family": "Microsoft YaHei",
        "font_family_en": "Arial",
        "chart_border": False,
        "grid_style": {"alpha": 0.2, "linestyle": "--", "linewidth": 0.35},
        "spine_style": {"visible": True, "color": "#CCCCCC", "linewidth": 0.4},
        "data_label": {"fontsize": 7.5, "color": "#444444", "format": "{:.1f}"},
        "annotation_style": {"fontsize": 7, "color": "#888888"},
        "palette": ["#003366","#C41E3A","#666666","#4CB8E8","#999999",
                    "#D4AF37","#2E8B57","#8B4513","#9370DB","#708090"],
        "figure_prefix": "Figure ",
        "figure_separator": ": ",
    },
}


def find_chinese_font() -> Optional[str]:
    for fname in _CANDIDATE_FONTS:
        fpath = _FONTS_DIR / fname
        if fpath.exists():
            return str(fpath)
    if _FONTS_DIR.exists():
        for f in _FONTS_DIR.glob("*.ttf"):
            name_lower = f.name.lower()
            if any(k in name_lower for k in ["yahei", "simhei", "cjk", "han", "chinese"]):
                return str(f)
    return None


def setup_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    font_path = find_chinese_font()
    if font_path:
        font_manager.fontManager.addfont(font_path)
        font_name = font_manager.FontProperties(fname=font_path).get_name()
        plt.rcParams["font.family"] = [font_name, "sans-serif"]
        plt.rcParams["font.sans-serif"] = [font_name, "SimHei", "Microsoft YaHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        logger.info(f"Chinese font: {font_name} ({font_path})")
    else:
        plt.rcParams["font.family"] = ["sans-serif"]
        plt.rcParams["axes.unicode_minus"] = False
        logger.warning("No Chinese font found")

    plt.rcParams.update({
        "font.size": 10, "font.weight": "normal",
        "axes.titlesize": 13, "axes.labelsize": 10,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "legend.fontsize": 9,
        "figure.dpi": 150, "savefig.dpi": 200,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.3,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.3,
        "grid.linestyle": "--", "grid.linewidth": 0.5,
    })
    return plt


def load_colors_from_templates() -> dict[str, dict]:
    colors = {}
    if not _TEMPLATES_DIR.exists():
        return colors
    for inst_dir in sorted(_TEMPLATES_DIR.iterdir()):
        if inst_dir.is_dir():
            json_path = inst_dir / "colors.json"
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    raw_palette = data.get("chart_palette", data.get("palette",
                        ["#003366","#C41E3A","#E8C84C","#4CB8E8","#666666"]))
                    colors[inst_dir.name] = {
                        "primary": data.get("primary", "#003366"),
                        "accent": data.get("accent", "#C41E3A"),
                        "secondary": data.get("secondary", "#666666"),
                        "bg": data.get("background", data.get("bg", "#FFFFFF")),
                        "text": data.get("text", "#1A1A1A"),
                        "palette": raw_palette,
                    }
                except Exception as e:
                    logger.warning(f"Failed to load {inst_dir.name} colors: {e}")
    return colors


def apply_institution_style(ax, inst_palette: dict, title: str = "",
                            figure_num: int = None, data_source: str = ""):
    """Apply full institution-specific styling to a matplotlib axes."""
    if figure_num is not None:
        prefix = inst_palette.get("figure_prefix", "Figure ")
        sep = inst_palette.get("figure_separator", ": ")
        full_title = f"{prefix}{figure_num}{sep}{title}"
    else:
        full_title = title

    if full_title:
        ax.set_title(full_title, fontsize=13, fontweight="bold",
                     color=inst_palette.get("primary", "#003366"), pad=14)

    spine_style = inst_palette.get("spine_style", {})
    for spine_name in ["top", "right"]:
        ax.spines[spine_name].set_visible(False)
    for spine_name in ["bottom", "left"]:
        if spine_style.get("visible", True):
            ax.spines[spine_name].set_color(spine_style.get("color", "#CCCCCC"))
            ax.spines[spine_name].set_linewidth(spine_style.get("linewidth", 0.4))
        else:
            ax.spines[spine_name].set_visible(False)

    grid_style = inst_palette.get("grid_style", {})
    ax.grid(True, alpha=grid_style.get("alpha", 0.2),
            linestyle=grid_style.get("linestyle", "--"),
            linewidth=grid_style.get("linewidth", 0.35),
            color=inst_palette.get("grid", "#E8E8E8"))
    ax.set_axisbelow(True)
    ax.set_facecolor(inst_palette.get("bg", "#FFFFFF"))
    ax.tick_params(colors=inst_palette.get("text", "#333333"), labelsize=8)

    if data_source:
        fig = ax.figure
        fig.text(0.99, 0.01, f"Source: {data_source}",
                 fontsize=7, color=inst_palette.get("annotation_style", {}).get("color", "#999999"),
                 ha="right", va="bottom")


def format_value(val, fmt_str: str = "{:.1f}") -> str:
    if abs(val) >= 1_000_000_000:
        return f"{val/1e9:.1f}B"
    elif abs(val) >= 1_000_000:
        return f"{val/1e6:.1f}M"
    elif abs(val) >= 1_000:
        return f"{val/1e3:.1f}K"
    elif isinstance(val, float) and 0 < abs(val) < 1:
        return f"{val*100:.1f}%"
    else:
        return fmt_str.format(val)


_inited = False
PALETTES: dict[str, dict] = {}


def ensure_init():
    global _inited, PALETTES
    if not _inited:
        setup_matplotlib()
        PALETTES.update(INSTITUTION_PALETTES)
        
        # Merge 505-extracted style DNA (overrides hand-written where available)
        try:
            dna_path = _PROJECT_ROOT / "data" / "505_institution_style_dna.json"
            if dna_path.exists():
                with open(dna_path, "r", encoding="utf-8") as f:
                    dna_data = json.load(f)
                dna_insts = dna_data.get("institutions", {})
                id_map = {
                    "gs": "gs", "ms": "ms", "mck": "mck", "bcg": "bcg",
                    "bain": "bain", "accenture": "accenture", "pwc": "pwc",
                    "ey": "ey", "kpmg": "kpmg", "cicc": "cicc", "citic": "citic",
                }
                for dna_id, dna_colors in dna_insts.items():
                    chart_key = id_map.get(dna_id)
                    if not chart_key or chart_key not in PALETTES:
                        continue
                    palette = dna_colors.get("palette", [])
                    fonts = dna_colors.get("font_families", [])
                    if palette:
                        clean = ["#" + c if not c.startswith("#") else c for c in palette[:10]]
                        PALETTES[chart_key]["palette"] = clean
                        PALETTES[chart_key]["primary"] = clean[0] if len(clean) > 0 else PALETTES[chart_key].get("primary", "#003366")
                        PALETTES[chart_key]["accent"] = clean[1] if len(clean) > 1 else PALETTES[chart_key].get("accent", "#C41E3A")
                    if fonts:
                        PALETTES[chart_key]["font_family_en"] = fonts[0]
                    PALETTES[chart_key]["dna_source"] = "505_extracted"
                logger.info(f"Merged 505 DNA: {len(dna_insts)} institutions")
        except Exception as e:
            logger.debug(f"505 DNA merge skipped: {e}")
        
        template_colors = load_colors_from_templates()
        for key, val in template_colors.items():
            if key in PALETTES:
                # Merge template colors but extend palette to 10 colors
                old_palette = PALETTES[key].get("palette", [])
                PALETTES[key].update({k: v for k, v in val.items() if k != "palette"})
                new_palette = val.get("palette", [])
                # Prefer template palette, extend with INSTITUTION_PALETTES if shorter
                if len(new_palette) < len(old_palette):
                    PALETTES[key]["palette"] = new_palette + old_palette[len(new_palette):]
                else:
                    PALETTES[key]["palette"] = new_palette
            else:
                PALETTES[key] = val
        _inited = True


def get_palette(style_id: str = "cicc") -> dict:
    ensure_init()
    if style_id in PALETTES:
        return PALETTES[style_id]
    alias_map = {
        "goldman_sachs": "gs", "goldman": "gs",
        "morgan_stanley": "ms",
        "jpmorgan": "jpm", "jp_morgan": "jpm",
        "mckinsey": "mck",
    }
    resolved = alias_map.get(style_id)
    if resolved and resolved in PALETTES:
        return PALETTES[resolved]
    for key, palette in PALETTES.items():
        if style_id.startswith(key) or key.startswith(style_id):
            return palette
    return PALETTES.get("cicc", list(PALETTES.values())[0])


def list_palettes() -> list[str]:
    ensure_init()
    return sorted(PALETTES.keys())
