# V51 导出引擎现状

**DOCX**（`export/docx_exporter.py` + `export/docx_tables.py`）:
- 22 个富样式表格（交替行、深色表头、加粗首列、数字右对齐）
- 5 张图表嵌入
- 机构配色（GS、MS、McK、BCG 等 18 套）

**PPTX**（`export/pptx_exporter.py`）:
- 21 slide（覆盖全部章节）
- 5 张图表正确分配到关键词匹配的 slide（不重复）
- 使用 GS 的 `.potx` 模板（layuout 1/3/6 自动选择）
- 标题自动填入 placeholderd>

**当前差距 vs 你的要求（超过四大投行密度）：**
- PPTX 缺少表格嵌入（通过文字列表模拟，未用原生表格）
- 图表数量受限于 ChartEngine 生成数量（当前 4 张主图）
- 密度指标：字节跳动 24,491 字报告 → 22 表格 + 5 图表 = 每千字 1.1 个，高于中金均值 0.8/千字
