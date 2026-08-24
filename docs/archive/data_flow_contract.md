# 2号分析师 数据流契约 (Data Flow Contract)

## 架构原则
1. **数据必须流经所有层级**: DataPipeline 的输出必须同时注入 ChartPipeline 和 _write_report
2. **禁止编造**: DeepSeek 写作时必须收到实时数据约束，未提供的数据点必须标注为估算值
3. **门禁验证实质性内容**: IronGate 必须检查数据真实性，而非仅检查关键词存在

## 数据流图

```
User Input (asset/type/style)
  |
  |-- DataPipeline (Crawl4AI + akshare)
  |     |
  |     |-- chart_data --> ChartPipeline (图表生成)
  |     |
  |     |-- financials --> _write_report (数据注入 prompt)
  |     |
  |     |-- news --> _write_report (数据注入 prompt)
  |
  |-- _write_report (DeepSeek + 实时数据约束)
  |     |
  |     |-- report_text --> IronGate (22项检查 + DataFidelityGate)
  |
  |-- ReportExporter (MD -> DOCX + PPTX + PDF)
  |     |
  |     |-- VisualGate (排版质量检查)
  |
  |-- LearningLoop (记录门禁结果)
```

## 数据契约 (接口定义)

### DataPipeline.collect() -> dict
```python
{
    "asset": str,           # "芯联集成 688469.SH"
    "report_type": str,     # "listed_company"
    "sources": dict,        # {"akshare": "ok", "crawl4ai_news": "ok"}
    "financials": {         # 来自 akshare
        "revenue": {"2021": 32.0, ...},   # 营收(亿元)
        "profit": {"2021": -4.8, ...},    # 净利润(亿元)
        "margin": {"gross_2021": 15.0},   # 毛利率(%)
        "source": "akshare"
    },
    "chart_data": {
        "revenue_trend": {...},
        "profit_trend": {...},
        "market_share": {...},
        "valuation": {...},
    },
    "news": [str],          # Crawl4AI 爬取的新闻文本
}
```

### chart_pipeline.generate_all(data) -> dict[str, str]
- 输入: data_pipeline 输出 dict
- 输出: chart_id -> file_path 映射

### _write_report(chart_paths, data) -> str
- 输入: chart_paths + data_pipeline 输出
- 输出: Markdown 报告文本
- 约束: 必须将 data["financials"] 注入 DeepSeek prompt

## 验证标准
1. DeepSeek prompt 必须包含 "REAL-TIME DATA" 约束块
2. 报告中的营收/利润数据必须与 data_pipeline 采集的数据偏差 < 20%
3. 每个关键数据点必须有数据源标注
4. 所有 4 种输出格式 (DOCX/PPTX/PDF/MD) 必须使用同一份报告文本

## 版本历史
- V1: 基础管线 (数据不注入写作层 - 已淘汰)
- V2: 数据注入写作层 + DataFidelityGate
