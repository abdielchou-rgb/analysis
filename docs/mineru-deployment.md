# MinerU 部署说明（Claude 全局 + 2hao-analyst）

> 部署日期：2026-08-10 · 交付物：`core/mineru_parser.py` + `skills/mineru/SKILL.md` + `scripts/install_mineru_windows.bat`
> 目标：Claude 全局可调用 MinerU（CLI skill + MCP Server 双通道），2hao 项目内可通过 Python 封装直接提取研报/年报/任意文档。

---

## 1. MinerU 是什么

OpenDataLab 开源的**文档解析引擎**：把非结构化文档（PDF / 图片 / DOCX / PPTX / XLSX）转成 LLM 友好的 Markdown / JSON。
- 支持扫描版、手写、多栏版面、跨页表格合并、公式 → LaTeX
- 109 种语言 OCR，VLM + OCR 双引擎
- 自动去页眉页脚，按人类阅读顺序输出

**解决 2hao 现有痛点**：`baseline_pdf_extractor` / `methodology_pdf_extractor` 用 pdfplumber（仅文本层），扫描版/复杂版面提取为空或乱。MinerU 补强这一层。

---

## 2. 部署形态（三种能力，按需使用）

| 能力 | 形态 | 命令 | 免token | 限制 |
|------|------|------|---------|------|
| 本地离线引擎 | CLI | `mineru -p 文件 -o 目录` | ✅ | 首次下载模型 ~3GB |
| 云 Flash | CLI | `mineru-open-api flash-extract 文件` | ✅ | ≤20页 / ≤10MB |
| 云 Precision | CLI | `mineru-open-api extract 文件 -o 目录` | ❌需auth | ≤200页 / ≤200MB / 批量200个 |
| MCP Server | MCP 工具 | `uvx mineru-open-mcp` | ✅ | 同上（Flash 免 token） |

---

## 3. Windows 安装（一条命令）

```powershell
# 方式 A：运行交付脚本（管理员）
D:\2hao-analyst\scripts\install_mineru_windows.bat

# 方式 B：手动分步
python -m pip install mineru                # 本地引擎（可选，重）
python -m pip install mineru-open-sdk       # 云 CLI
python -m pip install mineru-open-mcp       # MCP Server
```

> ⚠️ **重要冲突**：本地引擎 `mineru` 与云 SDK `mineru-open-sdk` **都注册 Python 模块名 `mineru`**，同环境不可共存。
> 推荐：**全局装本地引擎**（离线可用、敏感文档不出机器），**MCP 用 uvx 隔离跑云**（不污染环境）。
> `core/mineru_parser.py` 已按接口差异（`process` vs `MinerU`）自动区分，auto 模式自动降级。

---

## 4. 接入 Claude 全局

### 4.1 MCP Server（Claude 桌面工具通道）

编辑 Claude 桌面配置文件（Windows：`%APPDATA%\Claude\claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "mineru": {
      "command": "uvx",
      "args": ["mineru-open-mcp"],
      "env": {
        "MINERU_API_TOKEN": ""          // 留空 = Flash 免 token；填 key = 启用 Precision
      }
    }
  }
}
```

重启 Claude 后，工具列表出现：`parse_documents`（PDF/DOCX/PPTX/图片/HTML → Markdown）、`get_ocr_languages`、`clean_logs`。

可选 HTTP 常驻模式（避免重复加载模型）：
```bash
MINERU_API_TOKEN=your_key mineru-open-mcp --transport streamable-http --port 8001
# 配置为 type: streamableHttp, url: http://127.0.0.1:8001/mcp
```

### 4.2 Skill（Claude 触发词通道）

- 项目内已写好：`skills/mineru/SKILL.md`（触发词：解析PDF / 研报转MD / 扫描版提取 / 文档结构化）
- 在 Claude 桌面应用里用 **save_skill** 安装为全局 skill（本次会话交付时已执行 `mcp__cowork__save_skill`），此后任何会话可直接触发。

---

## 5. 2hao-analyst 项目接入

### 5.1 Python 封装 `core/mineru_parser.py`

```python
from core.mineru_parser import MinerUClient, extract_markdown

md = extract_markdown("研报.pdf", mode="auto")  # auto: local→cloud 自动降级
# mode="local" 强制本地 | mode="cloud" 强制云
# kw: pages="1-20" 限页数；token= 传 API key
```

接口差异自动识别：装了本地引擎走本地，否则走云 Flash，都不可用则抛明确错误（不静默）。

### 5.2 建议接线点（研报/年报/知识吸收）

| 现有模块 | 现状 | MinerU 增强 |
|---------|------|-------------|
| `core/methodology_pdf_extractor.py` | v2 已接入：MinerU 优先+回退 | 扫描版/图文混排可换 `extract_markdown` |
| `core/baseline_pdf_extractor.py` | v3 已接入：MinerU 优先+回退 | 复杂版面/表格改用 MinerU（`--mineru` 开关） |
| `pipeline/knowledge_absorber.py` | 从基线抽取知识 | PDF 类基线文档可用 MinerU 提 MD 再注入 |
| `data/基线/` 批量 PDF | — | 批量：`mineru-open-api extract *.pdf -o out` |

**⚠️ 性能决策（实测数据，2026-08-10）**：
- MinerU **云 API 单份约 70s**（上传+排队+解析），适合**单份高价值文档**（复杂年报/扫描研报）
- pdfplumber **本地批量 8 份仅 2.4s**，适合**全量回测基线**（2651 份）
- `baseline_pdf_extractor.py` 默认 `use_mineru=False`（批量 pdfplumber），单份高价值文档手动 `extract_text(use_mineru=True)` 或 `python baseline_pdf_extractor.py --mineru --dir <目录>`

**建议优先级**：① 扫描版研报（pdfplumber 提取为空的场景，单份用 MinerU）② 年报三表页 ③ 方法论 PDF（图文混排）。

---

## 6. 常用命令速查

```bash
# 本地
mineru -p a.pdf -o ./out                       # 输出 ./out/a/a.md + images/
# 云 Flash
mineru-open-api flash-extract a.pdf -o ./out
# 云 Precision
mineru-open-api auth
mineru-open-api extract a.pdf -o ./out -f docx,latex,html
# 批量
mineru-open-api extract *.pdf -o ./results/
# MCP HTTP
mineru-open-mcp --transport streamable-http --port 8001
```

---

## 7. 验证清单

- [ ] `mineru --version` → 本地引擎可用
- [ ] `mineru-open-api flash-extract sample.pdf` → 输出 Markdown
- [ ] Claude 桌面 MCP 工具列表出现 `parse_documents`
- [ ] 2hao：`python -c "from core.mineru_parser import extract_markdown; print(extract_markdown('sample.pdf', mode='cloud')[:200])"`
- [ ] `mineru-open-api auth` 后 Precision 模式可用

---

## 8. 来源

- PyPI mineru: https://pypi.org/project/mineru/
- MinerU 官方文档: https://opendatalab.github.io/MinerU/
- MinerU-Ecosystem (CLI/SDK/MCP/skills): https://github.com/opendatalab/MinerU-Ecosystem
- MinerU-Document-Explorer MCP: https://github.com/opendatalab/MinerU-Document-Explorer
