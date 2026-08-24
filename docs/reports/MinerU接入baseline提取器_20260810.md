# MinerU 接入 baseline 提取器交付报告

> 日期：2026-08-10 · 承接上轮部署后的"实际接线"验证

## 本轮改动

| 文件 | 改动 | 说明 |
|------|------|------|
| `core/baseline_pdf_extractor.py` | v3 改造 | `extract_text` MinerU 优先 + pdfplumber 回退；`_strip_markdown` 剥离 Markdown 符号；`process_all` 支持 `--dir` + 回退目录 + `--mineru` 开关 |
| `core/mineru_parser.py` | 修复 | flash 模式补 `page_range` 参数（22页超限时报错不静默，修复前返回 None）；`ExtractResult` 状态检查 |
| `tests/test_mineru.py` | 新增 | 3 项：supports 判定 / Markdown 剥离 / 损坏 PDF 回退不崩溃 |

## 实测数据（关键决策依据）

| 场景 | 引擎 | 耗时 | 结论 |
|------|------|------|------|
| 8 份研报批量 | pdfplumber | **2.4s** | 批量首选 |
| 1 份研报 | MinerU 云 | **71s** | 单份高价值/复杂文档用 |
| 1 份 22页研报 | MinerU flash | 报错 -30003 | 已修复：传 page_range |

**结论**：`baseline_pdf_extractor` 默认 `use_mineru=False`（批量 pdfplumber 秒级），MinerU 作为**按需增强通道**（单份复杂文档 `extract_text(use_mineru=True)` 或 `--mineru --dir`）。

## 提取效果对比（同份研报：国元证券·厄尔尼诺专题）

- **pdfplumber**：前3页 4468 字，含 `[Table_...]` 模板残留标签，抓到 3 项（评级/分析师/预测）
- **MinerU**：前3页 2350 字，结构化 Markdown（标题层级清晰），抓到分析师（刘乐/杨磊）+预测+代码

两者正则后结果量级相当；MinerU 对扫描版/复杂版面价值最大（pdfplumber 提取为空场景）。

## 验证

- ✅ `py_compile` 两模块语法通过
- ✅ 新测试 `tests/test_mineru.py` 3 passed
- ✅ 相关回归 `test_fact_quality` + `test_consistency_engine` 21 passed（2 failed 为沙箱 docx 写权限限制，与本次改动无关）

## 限制说明

1. MinerU 云 API 单份 ~70s，**不适合全量批量**（2651 份基线库会跑数小时）
2. 本地引擎未装（用户 Windows 机需跑 `install_mineru_windows.bat`），当前沙箱走云 flash
3. 沙箱 2 个 docx 测试失败是 `output/` 写权限问题（memory 已有记录），非本次回归

## 2026-08-10 追加：methodology_pdf_extractor 同步接入

| 文件 | 改动 |
|------|------|
| `core/methodology_pdf_extractor.py` | v2：extract_pdf_text MinerU 优先+回退；`_strip_markdown`；`process_all` 支持 `--dir`/`--mineru` + 目录回退（原 METHODOLOGY_DIR 失效 → ifind研报） |

验证：语法 OK、单份 pdfplumber 提取 7038 字正常、3 份批量冒烟链路通（方法论命中取决于 PDF 主题）。
