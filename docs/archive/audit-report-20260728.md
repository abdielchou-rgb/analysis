# 2号分析师 模块完整性审计报告

> 日期: 2026-07-28
> 审计范围: 编码健康度 + 模块完整性 + 管线连接性 + 回传V30/V51精华

---

## 一、本次操作摘要

### ✅ 已完成修复（P0）

#### 1. 编码损坏修复（5个文件）
| 文件 | 问题 | 修复 |
|------|------|------|
| `pipeline/write_revise_loop.py` | LearningLoop注释3处乱码 | ✅ 恢复中文注释 |
| `pipeline/data_collector.py` | 搜索关键词4处乱码 | ✅ 恢复中文搜索词 |
| `pipeline/chart_data_adapter.py` | 字典键名乱码 | ✅ 恢复中文 |
| `pipeline/step_manager.py` | 全部中文注释乱码 | ✅ 全量重写 |
| `workflow.py` | 2处分隔线注释乱码 | ✅ 恢复 |

#### 2. ComputeEngine接入管线
- 在`write_revise_loop.py`中添加了财务计算阶段（Phase 1.5）
- 数据采集后 → 财务计算（收入桥、利润桥、DCF估值、可比估值、SOTP、情景分析）
- 计算结果注入 `data['compute_results']`，供SectionWriter使用时传递

#### 3. V30 Heritage框架恢复（7个模块）
| 模块 | 功能 | 复制到 |
|------|------|--------|
| `harvard_framework.py` | 哈佛四维分析（战略→会计→财务→前景） | ✅ compute/V30_compute/layer3_generate/heritage/ |
| `evidence_ladder.py` | 证据等级L1-L7分类器 | ✅ 同上 |
| `multi_institution_review.py` | 五机构视角评分 | ✅ 同上 |
| `honesty_boundary.py` | 诚实边界管理 | ✅ 同上 |
| `integrator.py` | 方法整合器 | ✅ 同上 |
| `paradigm_router.py` | 分析范式路由 | ✅ 同上 |
| `rule_priority.py` | 规则优先级 | ✅ 同上 |

#### 4. V30关键基础设施恢复
- `layer1_data/connectors/industry_chain.py` — 产业链连接器
- `layer1_data/connectors/hk_us_market.py` — 港美股连接器
- `layer1_data/data_fetcher.py` — 数据获取器
- `layer1_data/pipeline.py` — 数据管线
- `layer1_data/quality/validators.py` — 数据质量验证器
- `layer3_generate/agents/writer_agent.py` — 写作代理
- `layer3_generate/bluebook_integrator.py` — 蓝皮书集成
- `layer3_generate/quality_gate/text_gate.py` — 文本质量门禁
- `layer3_generate/templates/fill_template.py` — 模板填充
- `layer3_generate/templates/renderer.py` — 模板渲染
- `layer1_data/pipeline.py` — 数据管线
- `layer2_compute/valuation/global_benchmark.py` — 全球基准
- `layer2_compute/valuation/global_peers_db.py` — 全球同业数据库

#### 5. Iron Gate优化
- `min_charts` 从4恢复到5
- `min_chars` 保持 industry_deep=8000（✅ 合理值）

---

## 二、管线连接性审计

### 管线架构概览（修复后）

```
Phase 1/5: 数据采集（DataCollectorV5：Tavily + yfinance + akshare + StockSDK）
  ↓ data 字典（含 financials + chart_data）
Phase 1.5/5: 财务计算（ComputeEngine：RevenueBridge + MarginBridge + DCF + Comparable + SOTP + Scenario）
  ↓ data['compute_results']
Phase 2/5: 图表生成（ChartPlanner → ChartEngine）
  ↓ chart_paths
Phase 3-5/5: 写作→评审→改进循环（SectionWriter → Iron Gate + ProbabilisticDeepCheck）
  ↓ 通过 → Export（MD + DOCX）
```

### 核心模块激活状态

| 模块 | 位置 | 管线接入状态 |
|------|------|------------|
| **DataCollectorV5** | `pipeline/data_collector_v5.py` | ✅ 已接入 write_revise_loop |
| **ComputeEngine** | `pipeline/compute_engine.py` → `core/compute/*` | ✅ 已接入 Phase 1.5 |
| **ChartPlanner** | `pipeline/chart_planner.py` → `core/chart_engine.py` | ✅ 已接入 Phase 2 |
| **SectionWriter** | `pipeline/section_writer.py` | ✅ 已接入写循环 |
| **Iron Gate (16项检查)** | `pipeline/iron_gate.py` | ✅ 已接入 Phase 4 |
| **ProbabilisticDeepCheck** | `pipeline/probabilistic_deep_check.py` | ✅ 已接入 Phase 4 |
| **LearningLoop** | `pipeline/learning_loop.py` | ✅ 已接入（before/after report） |
| **FormatSheriff** | `pipeline/format_sheriff.py` | ✅ 已接入 Gate 前预处理 |
| **ReportWriter (export)** | `pipeline/report_writer.py` | ✅ 已接入导出 |
| **StepManager** | `pipeline/step_manager.py` | ✅ 已接入过程纪律 |

### ⚠️ 模块存在但未接入管线

| 模块 | 功能 | 是否应接入 |
|------|------|-----------|
| `core/argument.py` | ArgumentEngine — 分析论证框架 | ⚡ 应考虑引入 |
| `core/conviction.py` | 信度计算引擎 | ⚡ 应考虑引入 |
| `core/persuasion.py` | 说服力架构 | ⚡ 应考虑引入 |
| `core/hypothesis_verifier.py` | 假说验证器 | ⚡ 应考虑引入 |
| `core/methodology_injector.py` | 方法论注入器 | ⚡ 应考虑引入 |
| `core/report_blueprint.py` | 报告蓝本生成器 | ⚡ 应考虑引入 |
| `core/report_calibrator.py` | 报告校准器 | ⚡ 应考虑引入 |
| `core/data_provenance.py` | 数据溯源附录 | ⚡ 应考虑引入 |
| `core/scarcity_signals.py` | 稀缺信号检查 | 🔧 V51有但非关键 |
| `core/learn.py` / `core/edit.py` | 学习/编辑模块 | 🔧 LearningLoop已封装 |
| `core/style.py` / `core/verify.py` | 风格/验证 | 🔧 已有FormatSheriff替代 |
| `core/watchdog.py` | 监控模块 | 🔧 非核心分析功能 |

---

## 三、与V50+架构对比（T0-T3）

2号分析师的管线设计与V50+的T0-T3架构有本质区别：

| 架构层 | V50+（T0-T3） | 2hao（简化管线） | 评估 |
|--------|--------------|-----------------|------|
| T0: 输入/假设 | T0_input + T0_hypothesis + T0_research | 管线参数 `asset` + `report_type` | ⚡ 简化可接受 |
| T1: 知识 | T1_knowledge（orchestrator + data_engine + compute_engine + styles） | data_collector_v5 + compute/ | ✅ 功能等价更简洁 |
| T2a: 论证 | T2a_argument（engine + style_compiler） | section_writer（DeepSeek prompt生成） | ⚠️ 论证引擎未用 |
| T2b: 文风 | T2b_prose（engine + llm_client） | section_writer直接调用DeepSeek | ✅ 简化可接受 |
| T2x: 编辑 | T2x_edit（engine + learning_loop） | learning_loop.py | ✅ 功能等价 |
| T3: 交付 | T3_delivery + T3_verify | iron_gate + report_writer.export + format_sheriff | ✅ 更全面 |

评估：2hao的简化管线在功能上等价，但丢失了T2a_argument（论证引擎）的结构化论证能力。

---

## 四、数据驱动层审计

### 数据源集成状态
| 数据源 | 集成状态 | 备注 |
|--------|---------|------|
| Tavily（AI搜索） | ✅ DataCollectorV5 | SDK方式调用 |
| yfinance | ✅ DataCollectorV5 | 港美股数据 |
| akshare | ✅ DataCollectorV5 | A股数据 |
| StockSDK | ✅ DataCollectorV5 | A股资金流 |
| Crawl4AI | ❌ 未集成 | 应研究集成方式 |
| 政策/法规爬虫 | ❌ 未集成 | data/policy_crawler.py存在 |
| 卫星数据 | ❌ 未集成 | data/satellite_engine.py存在 |
| CVC数据 | ❌ 未集成 | data/cvc_engine.py存在 |
| 行业专属爬虫 | ✅ 部分 | 白酒/电池/新能源/光伏/半导体 |

注意：虽然 `data/` 目录下有policy_crawler, satellite_engine, cvc_engine等模块，但它们未被DataCollectorV5调用。这些是V51时代的功能模块，2hao的DataCollectorV5只使用了Tavily+yfinance+akshare+StockSDK。

---

## 五、学习回路审计

| 组件 | 状态 | 说明 |
|------|------|------|
| `core/edit_learn.py` | ✅ 存在 | EditDatabase — 编辑案例持久化 |
| `core/temporal_verifier.py` | ✅ 存在 | 时序预测记录 |
| `core/forward_picks.py` | ✅ 存在 | 前瞻判断追踪 |
| `core/calibration/dashboard.py` | ✅ 存在 | 校准仪表盘 |
| `pipeline/learning_loop.py` | ✅ 存在 | 集成封装层 |
| LearningLoop接入write_revise_loop | ✅ 已接入 | before_report + after_report |

学习回路完整，无需额外工作。

---

## 六、导出层审计

| 格式 | 状态 | 文件 |
|------|------|------|
| Markdown | ✅ 基础 | pipeline/report_writer.py |
| DOCX（Pandoc + python-docx双回退） | ✅ 完整 | export/docx_exporter.py |
| PPTX | ✅ 存在 | export/pptx_exporter.py |
| PDF | ✅ 存在 | export/pdf_exporter.py |
| 格式后处理 | ✅ 完整 | pipeline/format_sheriff.py + export/format_professionalizer.py |
| 视觉门禁 | ✅ 存在 | export/visual_gate.py |
| 内容密度门禁 | ✅ 存在 | export/content_density_gate.py |

导出层是2hao的相对优势——比V51更全面。

---

## 七、关键建议（按优先级）

### P0: 必须立即处理
1. **数据源全面激活** — DataCollectorV5应集成data/目录下的policy_crawler、satellite_engine、cvc_engine等模块
2. **Crawl4AI集成** — 增加Crawl4AI作为Tavily的补充/备选

### P1: 近期优化
3. **ArgumentEngine接入** — 将core/argument.py的论证框架接入section_writer，替换硬编码Prompt
4. **DataProvenance附录** — 将core/data_provenance.py的溯源机制接入导出环节
5. **多源交叉验证** — core/cross_validator.py已在report_writer中导入但未被调用

### P2: 战略升级
6. **Heritage框架管线化** — 将刚恢复的HarvardFramework、EvidenceLadder、MultiInstitutionReview接入V30_compute管线，使其在报告生成时被调用
7. **行业跟踪模块激活** — 研究engine/tracking/下的BCI、地理监控、comparison模块是否需要移植

---

## 八、总结

**2号分析师的系统完整性评估：**

- ✅ 编码健康度：全部修复
- ✅ 核心管线：完整（数据→计算→图表→写作→门禁→导出）
- ✅ V30计算层：完整复制（含Heritage框架）
- ✅ 学习回路：完整
- ✅ 导出层：比V51更全面
- ⚠️ 数据源：Tavily为主，政策/卫星/CVC等V51时代模块未接入
- ⚠️ 论证引擎：core/argument.py未接入管线
- ⚠️ 多源交叉验证：core/cross_validator.py导入但未调用
- ✅ Iron Gate：16项检查覆盖全面（min_charts=5, min_chars=8000）

**总评分：82/100** — 核心管线完整，数据源和论证引擎有显著优化空间。
