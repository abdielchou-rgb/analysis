---
name: mineru
description: MinerU 文档解析引擎——PDF/图片/DOCX/PPTX/XLSX → 高质量 Markdown/JSON。扫描版PDF、复杂版面、公式、表格一键结构化。触发词：解析PDF、研报转MD、扫描版提取、文档结构化、OCR转Markdown、mineru
---

# MinerU 文档解析 Skill

MinerU 是 OpenDataLab 开源的文档解析引擎，把非结构化文档（PDF/图片/DOCX/PPTX/XLSX）转成 LLM 友好的 Markdown/JSON，支持扫描版、手写、多栏、跨页表格、公式转 LaTeX。

## 触发
用户要求解析 PDF / 研报提取 / 扫描版文档 / 文档结构化 / 大文件转 Markdown 时加载。

## 两种引擎（自动降级）
| 模式 | 命令 | 条件 | 适用 |
|------|------|------|------|
| 本地离线 | `mineru -p 文件 -o 输出目录` | 已 `pip install mineru`，首次下载模型 ~3GB | 敏感文档/离线/大文件 |
| 云 Flash | `mineru-open-api flash-extract 文件` | 免 token，≤20页/10MB | 快速预览/小文件 |
| 云 Precision | `mineru-open-api extract 文件 -o 目录` | 需 `mineru-open-api auth` 登录 | 大文件/高保真/批量 |

## 调用步骤

### 1. 检查可用性
```bash
mineru --version          # 本地引擎
mineru-open-api --help    # 云 CLI（MinerU-Ecosystem）
```

### 2. 本地解析单个 PDF
```bash
mineru -p 研报.pdf -o ./output/
# 输出：./output/研报/研报.md + images/ + xxx.json
```

### 3. 云 Flash（免 token，快）
```bash
mineru-open-api flash-extract 研报.pdf
mineru-open-api flash-extract 研报.pdf -o ./out   # 保存全部资源
```

### 4. 云 Precision（登录后，保真高）
```bash
mineru-open-api auth        # 首次登录
mineru-open-api extract 研报.pdf -o ./out
mineru-open-api extract 研报.pdf -f docx,latex,html -o ./out   # 多格式导出
```

### 5. 批量
```bash
mineru-open-api extract *.pdf -o ./results/
mineru-open-api extract --list 文件清单.txt -o ./results/
```

## 2hao 项目内调用（Python 封装）
```python
from core.mineru_parser import extract_markdown

md = extract_markdown("研报.pdf", mode="auto")  # auto: local→cloud 降级
```
- `mode="local"` 强制本地；`mode="cloud"` 强制云
- 传 `pages="1-20"` 限制页数（云 Flash 上限 20 页）
- 设环境变量 `MINERU_API_TOKEN` 可启用云 Precision

## 与 pdfplumber / pdf skill 的分工
- **pdfplumber**：现有 baseline/methodology 提取器，纯文本层，快，适合文本型 PDF
- **pdf skill**：PDF 阅读/合并/拆分/水印/填表等文档操作
- **MinerU**：复杂文档结构化（扫描版 OCR、版面重建、公式表格）——需要高质量提取时优先

## 质量提示
1. 扫描版/图片型 PDF 必须走 MinerU（pdfplumber 提取为空）
2. Flash 模式 ≤20 页，大文件用 Precision 或本地
3. 提取结果含路径引用（images/）时，交付给用户需连资源目录一起
