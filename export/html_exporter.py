"""
HTML 报告导出器 — R30 模块3（排版修复）：排版中立解

DOCX 空段落、PPTX 0图暴露导出链路脆弱。HTML 是排版的"中立解"：
- 图表 base64 内嵌（治图表找不到问题）
- 表格、TOC、样式统一
- 无空白页问题（浏览器自适应）

用法：export_html(md_text, output_path, chart_paths, title)
"""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path

logger = logging.getLogger("2hao.html_exporter")

_ROOT = Path(__file__).resolve().parent.parent

# 机构风格配色
STYLE_CICC = {
    "primary": "#003366",
    "accent": "#c8102e",
    "bg": "#ffffff",
    "text": "#1a1a1a",
    "muted": "#666666",
    "border": "#e0e0e0",
}


def _img_to_base64(path: str) -> str:
    """PNG 转 base64。"""
    try:
        data = Path(path).read_bytes()
        return "data:image/png;base64," + base64.b64encode(data).decode()
    except Exception:
        return ""


def _extract_chart_refs(md_text: str) -> list[str]:
    """从 markdown 提取图表引用 ![](chart:fig_id)。"""
    return re.findall(r"!\[[^\]]*\]\(chart:([\w_]+)\)", md_text)


def _md_to_html(md_text: str) -> str:
    """简单 markdown → html（标题/表格/段落/粗体）。"""
    lines = md_text.split("\n")
    html_parts = []
    in_table = False
    table_rows = []
    for line in lines:
        s = line.strip()
        # 表格
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.split("|")[1:-1]]
            if "---" in s:
                continue
            table_rows.append(cells)
            in_table = True
            continue
        if in_table:
            if not table_rows:
                continue
            html_parts.append("<table>")
            if table_rows:
                html_parts.append("<tr>" + "".join(f"<th>{c}</th>" for c in table_rows[0]) + "</tr>")
                for row in table_rows[1:]:
                    html_parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
            html_parts.append("</table>")
            table_rows = []
            in_table = False
        # 标题
        if s.startswith("### "):
            html_parts.append(f"<h3>{s[4:]}</h3>")
        elif s.startswith("## "):
            html_parts.append(f"<h2>{s[3:]}</h2>")
        elif s.startswith("# "):
            html_parts.append(f"<h1>{s[2:]}</h1>")
        elif s.startswith("---"):
            html_parts.append("<hr/>")
        elif s.startswith("!["):
            html_parts.append(f"<p class='chart-ref'>{s}</p>")
        elif s:
            # 粗体
            s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
            html_parts.append(f"<p>{s}</p>")
    if in_table and table_rows:
        html_parts.append("<table><tr>" + "".join(f"<th>{c}</th>" for c in table_rows[0]) + "</tr></table>")
    return "\n".join(html_parts)


def export_html(report_md: str, output_path: str, chart_paths: dict = None, title: str = "深度研究报告") -> str:
    """导出 HTML 报告。返回输出路径。"""
    style = STYLE_CICC
    # 解析图表引用 → 内嵌 base64
    chart_refs = _extract_chart_refs(report_md)
    chart_html = ""
    # 尝试从 chart_paths 或自动发现
    if chart_paths:
        for cid, path in sorted(chart_paths.items()):
            b64 = _img_to_base64(str(path))
            if b64:
                chart_html += f"<figure><img src='{b64}' alt='{cid}'/><figcaption>{cid}</figcaption></figure>\n"
    if not chart_html:
        # 自动发现 output/charts
        charts_dir = _ROOT / "output" / "charts"
        if charts_dir.exists():
            for p in sorted(charts_dir.glob("*.png"))[:30]:
                b64 = _img_to_base64(str(p))
                if b64:
                    chart_html += (
                        f"<figure><img src='{b64}' alt='{p.stem}'/><figcaption>{p.stem}</figcaption></figure>\n"
                    )

    body = _md_to_html(report_md)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
:root {{ color-scheme: light; }}
body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
       color: {style["text"]}; background: {style["bg"]}; margin: 0; padding: 24px; line-height: 1.7; }}
h1 {{ color: {style["primary"]}; border-bottom: 3px solid {style["accent"]}; padding-bottom: 8px; }}
h2 {{ color: {style["primary"]}; border-left: 4px solid {style["accent"]}; padding-left: 8px; margin-top: 32px; }}
h3 {{ color: {style["primary"]}; }}
table {{ border-collapse: collapse; margin: 16px 0; width: 100%; }}
th {{ background: {style["primary"]}; color: #fff; padding: 8px; text-align: left; }}
td {{ border: 1px solid {style["border"]}; padding: 8px; }}
tr:nth-child(even) {{ background: #f7f7f7; }}
figure {{ margin: 16px 0; text-align: center; }}
figure img {{ max-width: 100%; height: auto; border: 1px solid {style["border"]}; border-radius: 4px; }}
figcaption {{ color: {style["muted"]}; font-size: 13px; margin-top: 4px; }}
hr {{ border: none; border-top: 1px solid {style["border"]}; margin: 24px 0; }}
.chart-ref {{ color: {style["muted"]}; font-size: 13px; }}
p {{ margin: 8px 0; }}
</style>
</head>
<body>
{body}
<hr/>
<h2>数据图表</h2>
{chart_html}
</body>
</html>"""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    logger.info("[HTML-EXPORT] %s (%d bytes)", out, len(html))
    return str(out)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(_ROOT))
    md = open(str(_ROOT / "output" / "柯力传感_cicc.md"), encoding="utf-8").read()
    out = export_html(md, str(_ROOT / "output" / "test_keli.html"), title="柯力传感深度报告")
    print("HTML 导出:", out, Path(out).stat().st_size, "bytes")
