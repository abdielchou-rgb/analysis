## 管线架构

```
scheduler.py (唯一入口)
  └→ E2EOrchestratorV2
       ├→ preflight — 运行环境检查
       ├→ data_collect — 采集数据（akshare / Tavily / yfinance）
       ├→ chart_gen — 生成图表（ChartEngine / placeholder fallback）
       ├→ compute — 执行计算管线（DCF / 可比 / 场景分析）
       ├→ section_writer — SAC 驱动三段写作
       ├→ iron_gate — 24 项质量检查
       ├→ export — 导出 DOCX + 门禁检查
  └→ IronGate (24 项检查, min_score=0.55)
  └→ export (DOCX / PDF / PPTX)
```
