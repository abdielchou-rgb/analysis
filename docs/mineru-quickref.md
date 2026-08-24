# 2hao 文档解析能力速查卡

> 2026-08-10 · MinerU 全链路部署完成后的用法速查。覆盖 4 通道 + 3 场景 + 1 决策表。

---

## 一、四通道怎么选

| 通道 | 触发/调用 | 适合 | 成本 |
|------|-----------|------|------|
| **Claude Skill** | 对话里说"解析这份PDF/研报转MD/扫描版提取" | Claude 自动调 MinerU，最省心 | 自动（本地→云降级） |
| **MCP 工具** | Claude 桌面工具列表 `parse_documents` | Agent 流程内直接调，可编程 | Flash 免token |
| **Python 封装** | `from core.mineru_parser import extract_markdown` | 2hao 管线内嵌、批量前处理 | 自动 |
| **CLI 直用** | `mineru` / `mineru-open-api` | 终端手动、脚本 cron | 本地免费 / 云Flash免费 |

---

## 二、三个核心场景

### 场景 A：研报/PDF 知识提取（最高价值）
```python
from core.mineru_parser import extract_markdown
md = extract_markdown("研报.pdf", mode="auto", page_range="1-20")
# → 结构化 Markdown，供 data_basement / knowledge_injector 注入
```
- 单份高价值研报：**MinerU**（扫描版/复杂版面也能抓）
- 全量回测基线（2651份）：**pdfplumber**（`baseline_pdf_extractor.py` 默认）

### 场景 B：财报/年报解析
```bash
# 三表页常是复杂版面，MinerU 表格→HTML 比 pdfplumber 准
mineru -p 年报.pdf -o ./out            # 本地
mineru-open-api extract 年报.pdf -o ./out -f html   # 云 precision
```

### 场景 C：通用文档转 MD
```bash
mineru-open-api flash-extract 任意.pptx -o ./out    # 免token
mineru-open-api extract *.pdf -o ./results/          # 批量
```

---

## 三、决策表：批量 vs 单份（实测数据）

| 场景 | 引擎 | 耗时 | 结论 |
|------|------|------|------|
| 8 份研报批量 | pdfplumber | **2.4s** | ✅ 批量首选 |
| 1 份研报 | MinerU 云 | **71s** | ⚠️ 仅单份高价值/复杂文档 |
| 1 份 22页研报 | MinerU flash | 报错→已修复 | 传 `page_range` |

**铁律**：批量永远 pdfplumber；MinerU 只用于单份扫描版/复杂版面/高保真需求。

---

## 四、Claude MCP 配置（复制即用）

**Windows 路径**：`%APPDATA%\Claude\claude_desktop_config.json` 的 `mcpServers` 里加：

```json
{
  "mcpServers": {
    "mineru": {
      "command": "uvx",
      "args": ["mineru-open-mcp"],
      "env": {
        "MINERU_API_TOKEN": ""
      }
    }
  }
}
```

重启 Claude → 工具列表出现 `parse_documents` / `get_ocr_languages` / `clean_logs`。

> 填 `MINERU_API_TOKEN`（https://mineru.net 申请）可启用 Precision 高保真模式（≤200页/200MB/批量200个）。

---

## 五、已接线模块清单

| 模块 | 版本 | MinerU 增强 | 目录回退 |
|------|------|------------|----------|
| `core/mineru_parser.py` | — | 封装（local/cloud 自动降级） | — |
| `core/baseline_pdf_extractor.py` | v3 | ✅ `--mineru` 开关 | 回测基线库→ifind研报 |
| `core/methodology_pdf_extractor.py` | v2 | ✅ `--mineru` 开关 | 方法论目录→ifind研报 |
| `tests/test_mineru.py` | — | 3 passed | — |

---

## 六、常见坑

1. **模块名冲突**：`mineru`（本地）与 `mineru-open-sdk`（云）同名，**同环境不可共存**——封装已按接口差异自动区分
2. **flash 限 20 页**：超限报 `-30003`，必须传 `page_range="1-20"`
3. **扫描版**：pdfplumber 提取为空 ≠ 文档没字，换 MinerU
4. **交付带资源**：MinerU 输出的 images/ 引用需连目录一起给用户

---

> 详细部署见 `docs/mineru-deployment.md`；接入验证见 `docs/reports/MinerU接入baseline提取器_20260810.md`
