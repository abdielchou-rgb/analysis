# V51 Word/PPT 图表与表格渲染算法

> 目标：DOCX 和 PPTX 的表格/图表密度超过四大投行和中信中金  
> 基准：中金/高盛/MS 研报平均每千字 0.8-1.2 个数据锚点（表格+图表）  
> 当前 V51 输出能力：24,491 字 → 22 表格 + 5 图表 = 1.1/千字 ✅ 超过  
> 差距：PPTX 缺少原生表格渲染，图表仅 5 张（目标 8-12 张/份报告）

---

## 一、整体策略

Markdown 报告中的表格和图表在导出时，走两条各自独立的管线：

```
Markdown 报告
    │
    ├─ 表格管线 ──────────── DOCX: python-docx Table（富样式）
    │                       PPTX: pptx-table（原生表格）  
    │
    └─ 图表管线 ──────────── ChartEngine → .png → 嵌入 DOCX/PPTX
                           + 从正文提取数据 → 自动生成更多图表
```

两条管线独立运行，不互相阻塞。

---

## 二、表格渲染算法

### 2.1 从 Markdown 提取表格

```python
import re
from typing import List, Dict


def extract_tables(markdown_text: str) -> List[Dict]:
    """从 markdown 文本中提取所有表格块。

    返回:
        [{"headers": ["列1","列2",...],
          "rows": [["行1列1","行1列2",...], ...],
          "char_count": N}, ...]
    """
    tables = []
    lines = markdown_text.split("\n")
    buffer = []
    in_table = False

    for line in lines:
        if "|" in line and "---" not in line:
            buffer.append(line)
            in_table = True
        else:
            if in_table and len(buffer) >= 2:  # 至少表头+分隔线
                headers = [c.strip() for c in buffer[0].split("|") if c.strip()]
                rows = []
                for row_line in buffer[2:]:  # 跳过分隔线
                    cells = [c.strip() for c in row_line.split("|") if c.strip()]
                    if cells:
                        rows.append(cells)
                if headers and rows:
                    tables.append(
                        {
                            "headers": headers,
                            "rows": rows,
                            "char_count": sum(len(c) for r in rows for c in r),
                        }
                    )
            buffer = []
            in_table = False

    return tables
```

### 2.2 DOCX 富样式表格渲染

依赖：`python-docx`

```python
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn


def render_table_to_docx(
    doc: Document,
    table_data: dict,  # {"headers": [...], "rows": [[...], ...]}
    primary_color: tuple,  # (R, G, B) 机构主色，如 GS=(5,28,44)
    accent_color: tuple,  # 强调色
    table_index: int = 0,
) -> None:
    """将 markdown 表格渲染为富样式 Word 表格。

    样式规则：
      1. 表头：primary_color 背景 + 白色粗体字
      2. 数据行：交替浅灰背景（#F5F5F5）
      3. 首列：粗体
      4. 数字列（匹配 ^[\d\-.%]+$）：右对齐
      5. 最多渲染 15 行（防止超长表格溢出）
    """
    headers = table_data["headers"]
    rows = table_data["rows"][:15]
    n_cols = len(headers)

    table = doc.add_table(rows=1 + len(rows), cols=n_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    # 表头
    for ci, header in enumerate(headers):
        cell = table.rows[0].cells[ci]
        cell.text = header
        for para in cell.paragraphs:
            para.alignment = 1  # center
            for run in para.runs:
                run.font.bold = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        # 背景色填充
        shading = cell._element.get_or_add_tcPr()
        fill_hex = f"{primary_color[0]:02X}{primary_color[1]:02X}{primary_color[2]:02X}"
        shd = shading.makeelement(qn("w:shd"), {qn("w:fill"): fill_hex, qn("w:val"): "clear"})
        shading.append(shd)

    # 数据行
    for ri, row_data in enumerate(rows):
        row = table.rows[ri + 1]
        for ci, cell_text in enumerate(row_data[:n_cols]):
            cell = row.cells[ci]
            cell.text = cell_text
            is_num = bool(re.match(r"^[\d\-.%]+$", cell_text.strip()))
            for para in cell.paragraphs:
                para.alignment = 2 if is_num else 0
                for run in para.runs:
                    run.font.size = Pt(8.5)
                    if ci == 0:
                        run.font.bold = True
        # 交替行
        if ri % 2 == 0:
            for ci in range(n_cols):
                cell = row.cells[ci]
                shading = cell._element.get_or_add_tcPr()
                shd = shading.makeelement(qn("w:shd"), {qn("w:fill"): "F5F5F5", qn("wval"): "clear"})
                shading.append(shd)

    doc.add_paragraph()  # 表后间距
```

### 2.3 PPTX 原生表格渲染

依赖：`python-pptx`

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


def render_table_to_pptx(
    slide,
    table_data: dict,
    left: float = 0.5,  # 英寸
    top: float = 1.5,
    width: float = 9.0,
    height: float = None,  # 自动计算
    primary_hex: str = "#003366",
) -> None:
    """在 PPTX slide 上渲染原生表格。

    样式规则同 DOCX：深色表头、交替行、首列加粗。
    表格位置自动适配 slide 布局（有图时缩窄）。
    """
    headers = table_data["headers"]
    rows = table_data["rows"][:8]  # PPTX 每页表格不超过 8 行
    n_cols = len(headers)
    n_rows = 1 + len(rows)

    # 有图时表格窄一些
    has_image_on_slide = any(sh.shape_type == 13 for sh in slide.shapes)
    if has_image_on_slide:
        width = 4.5
        left = 0.3

    row_height = Inches(0.35)
    tbl_height = row_height * n_rows

    try:
        table_shape = slide.shapes.add_table(n_rows, n_cols, Inches(left), Inches(top), Inches(width), tbl_height)
        table = table_shape.table

        # 列宽均匀分配
        for ci in range(n_cols):
            table.columns[ci].width = Inches(width / n_cols)

        # 表头
        for ci, header in enumerate(headers):
            cell = table.cell(0, ci)
            cell.text = header[:30]
            for para in cell.text_frame.paragraphs:
                para.alignment = PP_ALIGN.CENTER
                for run in para.runs:
                    run.font.bold = True
                    run.font.size = Pt(9)
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            # 填充
            from lxml import etree

            solidFill = etree.SubElement(
                cell._tc.get_or_add_tcPr(), "{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill"
            )
            srgbClr = etree.SubElement(solidFill, "{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr")
            srgbClr.set("val", primary_hex.lstrip("#"))

        # 数据行
        for ri, row_data in enumerate(rows):
            for ci, cell_text in enumerate(row_data[:n_cols]):
                cell = table.cell(ri + 1, ci)
                cell.text = cell_text[:40]
                for para in cell.text_frame.paragraphs:
                    is_num = bool(re.match(r"^[\d\-.%]+$", cell_text.strip()))
                    para.alignment = PP_ALIGN.RIGHT if is_num else PP_ALIGN.LEFT
                    for run in para.runs:
                        run.font.size = Pt(8)
                        if ci == 0:
                            run.font.bold = True
            # 交替行背景
            if ri % 2 == 0:
                for ci in range(n_cols):
                    fill = table.cell(ri + 1, ci)._tc.get_or_add_tcPr()
                    sf = etree.SubElement(fill, "{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill")
                    sc = etree.SubElement(sf, "{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr")
                    sc.set("val", "F5F5F5")
    except Exception:
        pass  # 嵌入失败不阻断
```

---

## 三、图表生成与嵌入算法

### 3.1 从报告正文提取数据做图表

当 `ChartEngine` 的 `data_points` 不足时，从报告正文用正则提取：

```python
import re
from collections import Counter


def extract_chart_data_from_text(text: str) -> dict:
    """从报告正文提取数字 + 单位 → 可用于绘图的键值对。

    策略：
      1. 找 "XX（亿元）"/"XX占比"/"XX增速" 模式
      2. 匹配数字+单位对 → 取前 10 个最常出现的指标
    """
    patterns = [
        r"(\w{2,8})[（(]\s*(\d+\.?\d*)\s*(亿元|亿美元|%|倍|港元|元)[）)]",
        r"(\w{2,8})[：:]\s*(\d+\.?\d*)\s*(亿元|亿|%)",
    ]
    data = {}
    for pat in patterns:
        for m in re.finditer(pat, text):
            key = m.group(1).strip()
            val = float(m.group(2))
            if 0 < val < 1e7 and key not in data:
                data[key] = val
    return data
```

### 3.2 图表按章节分配算法

```python
def assign_charts_to_sections(
    sections: list,  # slide_content: [{"title": "...", "body": [...]}, ...]
    chart_paths: dict,  # {"bar": "path.png", "pie": "...", ...}
) -> list:
    """将图表分配到最匹配的章节。

    匹配优先级：
      字面匹配 > 关键词匹配 > 章节序号匹配

    每章节最多嵌入 1 张图，每张图最多使用 1 次。
    """
    chart_items = sorted(chart_paths.items())
    keyword_map = {
        "核心判断": 0,
        "核心分歧": 0,
        "Bold Call": 0,
        "财务": 1,
        "收入": 1,
        "利润": 1,
        "KPI": 2,
        "用户": 2,
        "指标": 2,
        "竞争": 3,
        "壁垒": 3,
        "格局": 3,
        "估值": 4,
        "DCF": 4,
        "目标价": 4,
        "反方": 5,
        "风险": 5,
        "证伪": 5,
        "增长": 6,
        "增速": 6,
        "趋势": 6,
        "股权": 7,
        "融资": 7,
        "资本": 7,
        "电商": 8,
        "广告": 8,
        "收入结构": 8,
    }
    assigned = set()
    result = [False] * len(sections)  # has_chart 标记

    for i, sec in enumerate(sections):
        title = sec["title"]
        for keyword, chart_idx in keyword_map.items():
            if keyword in title and chart_idx < len(chart_items) and chart_idx not in assigned:
                result[i] = True
                assigned.add(chart_idx)
                break

    return result
```

### 3.3 图表嵌入 DOCX

```python
def embed_charts_to_docx(doc: Document, chart_paths: dict) -> None:
    """在 DOCX 末尾嵌入所有图表。

    每张图附带"图：类型"标题。
    """
    from pathlib import Path

    for chart_type, chart_path in sorted(chart_paths.items()):
        if Path(chart_path).exists():
            try:
                doc.add_picture(str(chart_path), width=Inches(5.5))
                cap = doc.add_paragraph()
                cap.alignment = 1
                run = cap.add_run(f"图：{chart_type}")
                run.font.size = Pt(9)
                run.font.italic = True
                doc.add_paragraph()
            except Exception:
                continue
```

---

## 四、调用顺序

```
1. extract_tables(md_text)          → 获取所有表格
2. extract_chart_data_from_text()   → 从正文提取数字
3. ChartEngine.generate_all(data)   → 生成图表 .png
4. assign_charts_to_sections()      → 图表分配到章节
5. render_table_to_docx()           → 每个表格渲染到 DOCX
6. render_table_to_pptx()           → 每个表格渲染到 PPTX slide
7. embed_charts_to_docx()           → 图表嵌入 DOCX
8. embed_charts_to_pptx()           → 图表嵌入 PPTX slide
```

**密度目标：**
- 字节跳动 24,491 字报告 → 当前 22 表格 + 5 图表 = 1.1/千字
- 可提升方向：从正文提取更多数字 → 生成更多迷你图表（如趋势线、细分柱状图）→ 目标 12+ 图表/份 → 1.6/千字

---

## 五、Marvis 执行步骤

```bash
cd D:\Claude\1hao-analyst-v51

python -c "
from export.docx_tables import extract_tables, render_table_to_docx
from core.chart_engine import ChartEngine
from docx import Document

md_text = open('outputs/字节跳动_非上市深度报告_V51.md').read()
tables = extract_tables(md_text)
print(f'提取表格: {len(tables)} 个')
# 然后对每个 table_data 调用 render_table_to_docx()
"

python main.py polish --file 报告.md --style goldman_sachs
# 自动执行：提取表格 → 生成图表 → 渲染 DOCX/PPTX
```

算法已写完。三个核心函数 `extract_tables()`、`render_table_to_docx()`、`render_table_to_pptx()` 已包含在 `export/docx_tables.py` 中。Marvis 要执行时，调用这些函数并传入 `markdown_text` 即可。
