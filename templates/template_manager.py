"""2号分析师 Template Manager"""

import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent
STYLE_MAP = {"# ": "Title", "## ": "Heading 1", "### ": "Heading 2", "#### ": "Heading 3", "##### ": "Heading 4"}
FONT_HIERARCHY = {
    "cicc": {
        "chinese_body": "宋体",
        "chinese_heading": "黑体",
        "english_body": "Times New Roman",
        "english_heading": "Arial",
        "size_title": 22,
        "size_h1": 16,
        "size_h2": 14,
        "size_h3": 12,
        "size_body": 10.5,
        "size_caption": 9,
        "size_footer": 8,
    }
}


def load_colors(style_id="cicc"):
    p = TEMPLATES_DIR / style_id / "colors.json"
    if p.exists():
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    return {
        "primary": "#003D7A",
        "secondary": "#C8962E",
        "accent": "#D4A843",
        "text": "#333333",
        "background": "#FFFFFF",
        "chart_palette": ["#003D7A", "#C8962E", "#D4A843", "#6B9BC4", "#E0C87D", "#8C8C8C"],
    }


def load_template(style_id="cicc"):
    p = TEMPLATES_DIR / style_id / "report.dotx"
    return p if p.exists() else None


def get_font_config(style_id="cicc"):
    return FONT_HIERARCHY.get(style_id, FONT_HIERARCHY["cicc"])


def get_style_for_heading(level):
    return ["Title", "Heading 1", "Heading 2", "Heading 3", "Heading 4"][min(level, 4)]


def hex_to_rgb(h):
    from docx.shared import RGBColor

    h = h.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
