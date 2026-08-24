"""V50+ ExpandableReport — brief/deep two-view HTML report.

A deliverable with two presentation layers:
- brief_view: condensed judgment-first cards, each expandable
- deep_view: full MECE deep analysis

Inspired by the muxuu "brief → expand" design pattern.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BriefCard:
    """A single expandable brief card."""
    title: str = ""
    content: str = ""
    expand_to_section_id: str = ""
    evidence_level: str = "b"  # a = strong, b = moderate, c = weak


@dataclass
class ChartRef:
    """Chart reference for embedding in reports."""
    path: str = ""
    caption: str = ""
    alt_text: str = ""


class ExpandableReport:
    """Two-view HTML report: brief → expand to deep."""

    def __init__(self, title: str = ""):
        self.title = title
        self.brief_cards: list[BriefCard] = []
        self.deep_sections: dict[str, str] = {}
        self.chart_paths: dict[str, str] = {}

    def to_html(self, report_title: str = "") -> str:
        """Generate a self-contained HTML page with expandable brief/deep cards."""
        title = report_title or self.title
        cards_html = ""
        for i, card in enumerate(self.brief_cards):
            deep_content = self.deep_sections.get(card.expand_to_section_id, "")
            chart_tag = ""
            for fmt, path in self.chart_paths.items():
                if fmt == "bar" and card.expand_to_section_id in path:
                    chart_tag = f'<img src="{path}" alt="{_html.escape(card.title)}" style="max-width:100%">'
                    break
            level_color = {"a": "#1a7f37", "b": "#9a6700", "c": "#cf222e"}.get(card.evidence_level, "#666")
            level_label = {"a": "高置信度", "b": "中等", "c": "低置信度"}.get(card.evidence_level, "")

            cards_html += f"""
            <div class="card" onclick="toggleSection('sec_{i}')">
                <div class="card-header">
                    <span class="evidence-badge" style="background:{level_color}">{level_label}</span>
                    <h3>{_html.escape(card.title)}</h3>
                    <span class="toggle-icon">+</span>
                </div>
                <div class="card-body" id="sec_{i}">
                    <p>{_html.escape(card.content)}</p>
                    {chart_tag}
                    {f'<div class="deep-content">{deep_content}</div>' if deep_content else ''}
                    <div class="expand-hint">点击收起</div>
                </div>
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
:root {{ color-scheme: light; }}
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #fafafa; color: #1a1a1a; }}
h1 {{ font-size: 1.6em; border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 20px; }}
.card {{ background: white; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; cursor: pointer; }}
.card-header {{ display: flex; align-items: center; gap: 12px; padding: 14px 16px; }}
.card-header h3 {{ margin: 0; font-size: 1em; flex: 1; }}
.evidence-badge {{ font-size: 0.7em; padding: 2px 8px; border-radius: 10px; color: white; white-space: nowrap; }}
.toggle-icon {{ font-size: 1.2em; font-weight: bold; color: #888; }}
.card-body {{ display: none; padding: 0 16px 16px; cursor: auto; }}
.card-body p {{ margin: 0 0 10px; line-height: 1.6; color: #444; }}
.deep-content {{ margin-top: 12px; padding: 12px; background: #f5f5f5; border-left: 3px solid #333; border-radius: 4px; font-size: 0.9em; line-height: 1.6; }}
.deep-content h2 {{ font-size: 1.1em; margin: 0 0 8px; }}
.expand-hint {{ text-align: center; color: #888; font-size: 0.8em; margin-top: 8px; }}
.card.open .card-body {{ display: block; }}
.card.open .toggle-icon {{ transform: rotate(45deg); }}
.footer {{ margin-top: 30px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 0.8em; color: #888; text-align: center; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div id="cards">{cards_html}</div>
<div class="footer">1号分析师 V50+ · 展开式简报</div>
<script>
function toggleSection(id) {{
    var el = document.getElementById(id);
    if (el) {{
        var card = el.closest('.card');
        if (card.classList.contains('open')) {{
            card.classList.remove('open');
        }} else {{
            // close all others
            document.querySelectorAll('.card.open').forEach(function(c) {{ c.classList.remove('open'); }});
            card.classList.add('open');
        }}
    }}
}}
</script>
</body>
</html>"""
        return html


