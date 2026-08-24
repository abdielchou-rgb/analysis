# 2hao-analyst 全量审计与工程推进计划

> 审计日期：2026-08-05  
> 审计对象：`D:\2hao-analyst`  
> 审计方式：静态代码核验 + 日志/数据/测试缓存证据 + 业界打法检索  
> 审计报告版本：v1  
> 结论一句话：**项目具备投行级研报生成的完整骨架，但“Gate 语义、入口一致性、安全配置、工程基线、FP 深水区”五项是当前最大负债；先止血，再免疫，后规模化。**

---

## 1. FP 理解

本项目的 FP 指 `docs/FP1-FP7-超级智能法则.md` 定义的第一性原理宪法（FP1-FP8）。产品定位是：

> 在 AI Agent 上运行、跨 A股/港股/美股、7×24 在线、在分析深度和广度上超越人类资深分析师的投行级中文研报生成系统。

八条 FP 的工程含义：

| FP | 含义 | 工程落点 |
|----|------|----------|
| FP1 | 系统本质 | 跨市场、7×24、可无 GUI 调用 |
| FP2a | 数据履约 | 零编造：A/E/F/B + source + 年份 + 口径 + 置信度 |
| FP2b | 分析履约 | 反方论证 + So What 链 + Bold Call |
| FP3 | 超级维度 | 速度/广度/深度/记忆/协作/持续 六维收敛 |
| FP4 | 人感约束 | 双阈值图灵测试：不像 AI + 有人类写不出的内容 |
| FP5 | 智能演化 | 每次分析、Gate 失败、人工反馈都要被学习 |
| FP6 | 推理透明 | L1-L6 分层可审计 |
| FP7 | 反脆弱性 | L1/L2/L3 三级降级 + 组件期权 + Agent 兜底必须回流管线 |
| FP8 | 元认知选择 | 先理解需求，再选框架/裁维度，事后反思 |

对应架构：`scheduler/main` → `E2EOrchestratorV2`（21 节点 AgentGraph）→ data/enrich → charts → compute → section_writer → StyleCompiler → IronGate（约 75 个检查方法）→ VisualGate + 管线指纹出口。

---

## 2. 独立核验事实

| 项目 | 实测值 |
|------|--------|
| Python 文件数 | 534（不含 `__pycache__`），约 9.3 万行 |
| 核心/管线/脚本/测试文件 | core 153 / scripts 73 / tests 55 / pipeline 43 |
| 数据目录 | 66,023 个文件，约 9.1 GB；`financials.db` 661 MB |
| pytest 缓存 | 308 个 node id；`lastfailed` 含 3 个 chart/standards 测试 |
| Harness 语法检查 | 25 个文件报错（根目录 BOM 调试脚本） |
| Gate 检查方法 | 75 个 `_check_*`，其中显式 `severity="error"` 约 19 个 |
| 文档口径 | README=34 项 / AGENTS=24 项 / FP 宪法=24 项 / r61=67 项 / r68=69 项 |
| 最近实跑 | 油位/柯力/集通均 3 轮 Gate 未过，无 DOCX；分数 0.80-0.87，偶见 1.67 |

---

## 3. 关键问题清单

### P0-1 出口门禁语义缺陷（最高优先级）

1. `GateCheckResult` 默认 `severity="warning"`，而 `IronGate.report.passed` 只统计 `severity == "error"` 的检查，大量核心检查失败不阻断。
2. `export_report` 出口只判断 `overall_score < min_score(0.55)`，**不判断 `report.passed`，也不使用 `gates_config.yaml` 的 `hard_fail` / `require_all_hard`**。
3. 日志出现 Gate score=1.673，分数未归一化到 [0,1]，阈值语义失真。
4. `main.py` 在 Gate 未通过时仍写 MD 并返回 `status: ok`，违反 FP7d。

涉及文件：

- `pipeline/checks/base.py`（severity 默认值）
- `pipeline/iron_gate.py`（passed 判定、overall_score 计算）
- `export/report_gate.py`（出口门禁判定）
- `export/gates_config.yaml`（hard_fail 配置未被消费）
- `main.py`（未过门禁仍写 MD）

### P0-2 主入口死代码与双入口不一致

1. `scheduler.py` 在 `E2EOrchestratorV2.run()` 后读取 `result["md"]`，但 orchestrator 返回结构中没有 `md` 字段，导致二次 IronGate、ChartEngine、强制出口三段**永远不会执行**。
2. `main.py` / `scheduler.py` 都没有把管线层 `pipe_gate_result` 传给 `export_report`，同一份报告会被 IronGate 重复跑，且参数不一致（`from_text` 不带 asset/degradation）。
3. 最近实跑均为 3 轮 Gate 未过，失败集中在 `sac_dims / charts / template_repeat / so_what_chain`；多次 `universe coverage 0.0-0.33 < 0.5`、Tavily 0 结果、图表 15/21 为 template 数据。

涉及文件：

- `pipeline/scheduler.py`
- `pipeline/e2e_orchestrator.py`
- `pipeline/data_enrichment.py`
- `pipeline/universe_build.py`

### P0-3 安全与密钥管理不合格

1. `.env` 明文存真实 DeepSeek/Tavily key。
2. Tavily key 泄漏在 `docs/archive/code-review-report.md` 和 `docs/data-enrichment-round4-marvis.md`。
3. Harness 的 API Key 扫描只扫 `.py/.bat`；`_self_audit` 跳过 `data/export/docs`，文档泄漏检测不到。
4. 项目没有 git 仓库；`.gitignore` 有 `*.md`，会把 README/CLAUDE/prompts/docs 全部忽略。
5. `pyproject.toml` build-backend 非标准（`setuptools.backends._legacy:_Backend`）；`requirements.txt` 与 pyproject 依赖漂移，无 lockfile。

### P1 架构、质量与测试

1. 上帝模块：`section_writer.py` 131KB、`e2e_orchestrator.py` 88KB、`compute_engine.py` 51KB、`chart_pipeline.py` 45KB。
2. 审计体系自相矛盾：Harness 语法检查报 25 个 BOM 文件失败，`_self_audit` 剥离 BOM 后报 PASS。
3. 计划中的基准文件缺失：`benchmark/calibrated_thresholds.json`、`data/industry_dimension_weights.json`、`core/bluebook/` 均不存在。
4. 根目录散落 24 个 BOM 调试脚本（`gate_v2*`、`fixgate*`、`temp_scan*`、`verify*` 等），`temp/` 还有 68 个文件。
5. `core/` 有 11 个疑似孤儿模块（`chart_caption`、`cognitive_transfer`、`findings_db`、`prediction_loop`、`price` 等）。
6. 测试基线 308 个 pytest node，`lastfailed` 有 3 个 chart/standards 测试；本环境无 python/pytest，未实跑。

### P2 FP 深水区未闭环

1. SAC 覆盖仍可被关键词命中游戏化。
2. InfoDesk（读者画像/行动问题）、跨报告关联、做空者视角、合规成本、替代 S 曲线、系统失效状态、资金面四层剥离均未接线。
3. FP3 六维测量未自动化；learning DB 落在 `output/`；预测闭环仍在积累期；chaos 注入未常态化。

---

## 4. 业界顶级打法

### 4.1 事实性/幻觉防线

- 分层防御：确定性 schema/算术/勾稽检查优先且免费，LLM 语义判断最后才跑。
- 引用必须是“真实存在的来源 + 原文 + 日期”，做不到就显式 `unavailable`。
- 生成与校验必须对侧 provider（自采自校验 = 幻觉双向通过）。
- 参考：MDPI 多层幻觉抑制框架、LSEG “licensed data + provenance + no-training rule”、世纪证券“数据分级 + 真实性追溯”、arXiv 2503.19848（防伪引用）。

### 4.2 结构化输出

- DeepSeek 等 API 场景：JSON Schema / `response_format` + 事后 schema 校验 + 重试。
- 离线评估 `schema_validity × semantic_quality`，警惕 constrained decoding 的“质量税”。
- 按模板路由，不是按应用一刀切。

### 4.3 Agent 可观测与持久化

- OpenTelemetry trace + Langfuse/LangSmith 全链路追踪。
- 长任务用 durable execution（Temporal），重试/状态可恢复可审计。

### 4.4 Eval 进 CI

- golden dataset（10-20 条起步）+ 确定性断言 + LLM judge + 成本/延迟预算。
- 作为 merge-blocking gate；生产失败自动沉淀为回归样例。

### 4.5 数据工程

- data contract + Great Expectations/dbt 测试 + freshness/coverage/对账。
- 字段级血缘；测试尽早做、聚焦关键列。

### 4.6 Prompt 版本化

- prompt 当代码管，A/B 对比 + 可回滚（Microsoft Foundry、AgentsKit）。

---

## 5. 工程推进计划

### Phase 0：止血与合规（1-2 天）

| # | 任务 | 涉及文件 | 验收 |
|---|------|----------|------|
| 0.1 | 轮换 DeepSeek/Tavily key，清文档泄漏，加 `.env.example` | `.env`、`docs/`、Harness | 全仓扫描 0 泄漏 |
| 0.2 | Harness key 扫描扩到 `.md/.json/docs` 并 P0 阻断 | `harness/validator.py`、`_self_audit.py` | 两套审计一致 |
| 0.3 | 修 Gate 语义：`passed` = hard_fail 全过 + score 达标 | `pipeline/iron_gate.py`、`pipeline/checks/base.py` | 回归测试覆盖 |
| 0.4 | `export_report` 必须用 `report.passed`/`hard_fail`，分数 clamp [0,1] | `export/report_gate.py` | 门禁不可被“高分绕过” |
| 0.5 | `main.py` Gate 失败不写 MD、返回 error | `main.py` | FP7d 合规 |
| 0.6 | scheduler 删除死代码，MD/DOCX 由管线单一出口产出 | `pipeline/scheduler.py` | 双入口一致 |
| 0.7 | `pipe_gate_result` 透传，消除 IronGate 双跑 | `main.py`、`scheduler.py`、`export/report_gate.py` | 单次调用 |
| 0.8 | `git init`、修 `.gitignore`、修 build-backend、依赖合一 + lockfile | 根配置 | `pip install .` 可安装 |
| 0.9 | 清根目录 BOM 脚本与 `temp/` 到 `archive/` | 根目录、`temp/` | 代码量下降 |

### Phase 1：数据可信与 Gate 免疫（3-5 天）

| # | 任务 | 涉及文件 | 验收 |
|---|------|----------|------|
| 1.1 | 数据契约：`chart_data/enrich_file/financials` 走 JSON Schema | `pipeline/data_enrichment.py`、`pipeline/data_collector.py` | 契约测试通过 |
| 1.2 | freshness/coverage/跨源对账（baostock vs akshare vs enrich） | `core/data_caliber.py`、sync 脚本 | 覆盖率报告可查 |
| 1.3 | `required_sub_elements` 全维度落地，Gate 子要素检查 | `core/sacs/*.yaml`、`pipeline/checks/coverage_mixin.py` | SAC 覆盖不可靠关键词刷分 |
| 1.4 | 补 `calibrated_thresholds.json` 默认档 | `benchmark/` | 阈值可校准可回退 |
| 1.5 | golden dataset + LLM judge rubric 接入 pytest 慢速套件 | `tests/golden/` | 每次 prompt 变更可回归 |

### Phase 2：可观测与演化闭环（3-5 天）

| # | 任务 | 涉及文件 | 验收 |
|---|------|----------|------|
| 2.1 | AgentGraph/LLM/数据源/Gate 全链路 OpenTelemetry + trace_id | `pipeline/e2e_orchestrator.py`、`pipeline/agent_graph.py` | 一次运行一条完整 trace |
| 2.2 | learning DB 移到 `data/`，加 recurrence 报表 | `pipeline/learning_loop.py` | 失败复发率可查 |
| 2.3 | 写改循环改可恢复状态机（SQLite checkpoint 或 Temporal） | `pipeline/e2e_orchestrator.py` | 中断后续跑不重头 |
| 2.4 | edit_learn 反馈端点和 3M/6M 短周期预测验证 | `core/edit_learn.py`、`core/forward_picks.py` | 反馈回路接通 |
| 2.5 | chaos 注入定期 job，断言 L1/L2/L3 降级 | `scripts/chaos_test.py` | 降级语义有测试 |

### Phase 3：架构治理与规模化（1-2 周）

| # | 任务 | 涉及文件 | 验收 |
|---|------|----------|------|
| 3.1 | 拆分上帝模块 | `pipeline/section_writer.py`、`pipeline/e2e_orchestrator.py` | 模块职责单一 |
| 3.2 | 文档单一事实源 + 自动生成 CLAUDE/AGENTS | `docs/`、`harness/generate_docs.py` | CI 校验一致 |
| 3.3 | Docker + GitHub Actions：单元测试、golden evals、安全扫描 | CI 配置 | PR 门禁生效 |
| 3.4 | scheduler 变成可排队服务 | `pipeline/scheduler.py` | 支持并发与重试 |

### Phase 4：FP 深水区（2-4 周）

| # | 任务 | 验收 |
|---|------|------|
| 4.1 | InfoDesk（reader_profile/action_questions） | 报告面向读者画像 |
| 4.2 | 跨报告 synthesis | 同赛道报告互引 |
| 4.3 | 5 个缺失维度（short-check/compliance cost/S-curve/sustained failure/capital flow 四层） | 对应 Gate 检查通过 |
| 4.4 | `industry_dimension_weights.json` + 数据驱动 planner | 20+ 报告后切换 |
| 4.5 | 美股/港股数据链路 + 7×24 定时调度 | FP1/FP3 可测量 |

---

## 6. 验证限制与下一步

1. 本次为只读沙箱，未实跑 pytest；现有缓存显示 308 个 node、3 个 lastfailed。
2. Phase 0 第一件事是搭可复现环境（`uv sync` + `pytest`），再改代码。
3. 所有关键修复先写回归测试，再改代码；避免继续“每版本加 R 号补丁”式演进。

---

## 7. 证据索引

- `pipeline/checks/base.py`：GateCheckResult severity 默认值
- `pipeline/iron_gate.py`：report.passed 判定、overall_score 计算
- `export/report_gate.py`：出口门禁只查 score
- `export/gates_config.yaml`：hard_fail 未消费
- `pipeline/scheduler.py`：`result["md"]` 死代码
- `main.py`：Gate 失败仍写 MD
- `docs/FP1-FP7-超级智能法则.md`：FP 宪法
- `docs/r74-master-engineering-plan.md`：已识别的 4 项系统性缺陷与 5 项缺失维度
- `docs/r68-module-audit.md`：18 个注入模块静默失败审计
