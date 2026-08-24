# 2号分析师 — 全量优化总结文档

> 日期: 2026-07-27
> 基于: 全量代码审计 + 圆桌会议 + First Principle
> 定位: 以First Principle为中心，对标世界顶级投行/咨询报告的质量系统

---

## 一、修复的P0问题

### 1.1 图表路径对齐（核心Bug）

**问题**: `workflow.py._step_charts()` 使用 `ChartRunner` 生成图表文件名为 `bar_cicc.png`、`line_cicc.png`，但 `ReportWriter.write_report()` 硬编码引用 `fig_market_size_global`、`fig_market_size_china` 等ID。两者完全不匹配 → DOCX中的图片全部断裂。

**修复**: 
- `_step_charts()` 改为使用 `ChartPlanner`（与 ReportWriter 共享相同图表ID方案）
- `ChartPlanner` 返回 `{chart_id: absolute_path}` 字典，key = `fig_market_size_global` 等
- `ReportWriter.write_report()` 的路径回退逻辑改为多候选搜索（优先用传入路径，然后 search 文件系统）
- 新增 `_get_plan_for_type()` 方法解决 `PLANS` 类属性引用 `self` 的问题

**验证**: 
- 6类图表全部正确生成 → `fig1_fig_market_size_global_cicc.png` 等
- ChartPlanner 返回6个正确ID的报告路径
- ReportWriter 能正确使用传入的路径字典

### 1.2 学习回路读端

**问题**: `EditCase`、`TemporalVerifier`、`ForwardPicks` 写入 SQLite，但没有任何代码读取。每次报告从零开始。

**修复**:
- `EditLearn`(EditDatabase) 新增 `get_by_asset()` 方法
- `workflow.py._step_write_loop()` 在写作前读取该资产的前5条失败经验
- 将学习反馈注入到 DeepSeek 的 `data_context` 中，让 AI 知道之前犯过什么错
- Gate重试循环也同样注入学习反馈

### 1.3 数据采集增强

**问题**: `DataCollector` 大部分数据源返回 `"unavailable"`，只有 akshare 和行业缓存偶尔命中。

**修复**:
- `_get_industry()` 新增第三层回退：使用 `requests` 进行 web search
- 搜索查询格式: `"{asset} 行业 市场规模 竞争格局 2024 2025"`
- 三层回退: akshare → 行业缓存 → web搜索

### 1.4 API密钥清理

**问题**: 硬编码 `<YOUR_DEEPSEEK_API_KEY>` 在3个文件中。

**修复**:
- `deepseek_client.py`: 密钥默认值改为空字符串 `""`，仅从环境变量读取
- `SKILL.md`: 硬编码密钥替换为 `<YOUR_DEEPSEEK_API_KEY>`
- `marvis_blind_test_instructions.md`: 同样清理

---

## 二、修复的P1问题

### 2.1 内容体积稳定性

- 写作循环阈值从 `8000` → `10000` 字符
- 图表数量阈值从 `3` → `5` 张

### 2.2 排版质量

- `FormatSheriff` 已实现三层防御：检测 → 自动修复 → 报告
- `FormatProfessionalizer` 处理加粗滥用、表格溢出、图片路径
- DOCX导出器支持20套机构模板样式配置文件

---

## 三、尚未解决的问题

### 3.1 分章节生成（P2）

当前问题：一篇报告一次性生成7000-10000字，LLM输出不稳定。

**建议方案**：
```python
# 按SAC因果链，每步200-400字，分7步生成
steps = ["稀缺层定位", "利润迁移路径", "竞争格局重构", 
         "技术路线验证", "市场空间校准", "政策传导检验", "资本市场映射"]
for step in steps:
    section = generate_section(step, data_for_step, charts_for_step)
    report.append(section)
```

### 3.2 更多数据源接入（P2）

当前问题：数据采集主要靠akshare和缓存，远不够专业报告所需。

**建议**：集成 Crawl4AI、Exa Search MCP、政府数据API

### 3.3 其他报告类型验证（P2）

当前只验证了 `industry_deep`。需要测试 `listed_company`、`unlisted_company`、`earnings_notes`。

---

## 四、核心质量保障体系

```
┌─────────────────────────────────────────────────┐
│              2号分析师 质量保障架构               │
├─────────────────────────────────────────────────┤
│  写作前: SAC → 数据采集 → 计算 → 图表规划        │
│  ─────────────────────────────────────────────  │
│  写作中: DeepSeek(含学习反馈) → ScoreEngine评分   │
│          → AIScanner → FormatSheriff             │
│          → 循环直到 ≥ 0.9                         │
│  ─────────────────────────────────────────────  │
│  写作后: Iron Gate(10项校验) → DOCX/MD导出        │
│  ─────────────────────────────────────────────  │
│  学习: EditCase写入 → 下次读取 → 持续改进         │
└─────────────────────────────────────────────────┘
```

### 评分维度 (8维)

| 维度 | 权重 | 及格线 | 检测方式 |
|------|------|--------|---------|
| AIGC指纹 | 15% | ≤ 0.15 | AIScanner |
| 人感 | 10% | ≥ 0.70 | HumanSenseDetector |
| 质量 | 20% | ≥ 0.80 | QualityScorer |
| SAC覆盖率 | 15% | ≥ 80% | Writing Charter |
| 图表密度 | 15% | ≥ 5张 | 正则统计 |
| 数据可追溯 | 10% | 有来源 | 正则 |
| 排版一致性 | 5% | 无问题 | FormatSheriff |
| 说服力架构 | 10% | 完整 | 关键词 |

---

## 五、运行方式

```powershell
# 设置API密钥
$env:DEEPSEEK_API_KEY = "sk-your-key-here"

# 运行行业深度报告
cd D:\\2hao-analyst
python main.py "商业航天" --type industry_deep --style cicc --output output9
```

---
