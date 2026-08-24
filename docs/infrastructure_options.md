# 基础设施期权清单

> 由 FP7c 驱动。每版本审查更新。
> 原则：每个关键组件至少有 2 个可替代实现。

| 组件 | 主选项 | 备选1 | 备选2 | 状态 |
|------|--------|-------|-------|------|
| **LLM Provider** | DeepSeek (deepseek-chat) | 阿里云 Qwen (qwen-plus) | OpenRouter (deepseek/deepseek-chat) | ✅ 3选项 |
| **A股数据** | akshare | StockSDK | 爬虫(financials via cninfo) | ✅ 3选项 |
| **国际数据** | yfinance | akshare国际 | - | ✅ 2选项 |
| **网络搜索** | Tavily | crawl4ai | Playwright | ✅ 3选项 |
| **图表生成** | ChartEngine (matplotlib) | ChartPipeline | ChartRunner占位图 | ✅ 3选项 |
| **DOCX 导出** | python-docx (exporter.py) | docx_exporter.py | - | ⚠️ 仅1实现 |
| **PDF 导出** | fpdf2 (pdf_exporter.py) | LibreOffice CLI | - | ⚠️ 仅1实现 |
| **报告验证** | IronGate (24+项) | visual_gate.py | content_density_gate.py | ✅ 3选项 |

## 单点故障风险 (SPOF)

| 组件 | 风险 | 缓解计划 |
|------|------|----------|
| DOCX 导出 | 只有 python-docx | 无紧急风险，python-docx 成熟 |
| PDF 导出 | 只有 fpdf2 | 考虑接入 WeasyPrint 或 Pandoc |
| LLM Provider | 框架支持多provider但实际注册只有DeepSeek | scheduler.py 已激活Qwen+OpenRouter，需验证.env 中有key |

## 切换时间估计

| 切换场景 | 自动/手动 | 估计时间 |
|----------|-----------|----------|
| DeepSeek 不可用 → Qwen | 自动 (circuit breaker) | < 30秒 |
| akshare 不可用 → StockSDK | 自动 (重试+fallback) | < 10秒 |
| Tavily 不可用 → crawl4ai | 自动 (multi-feeds) | < 60秒 |
| ChartEngine 失败 → 占位图 | 自动 (chart_runner fallback) | < 1秒 |
