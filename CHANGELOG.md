# 二号分析师 (2hao-analyst) CHANGELOG

## S1-S7 升级工程 (2026-09-01) — 27/27 子项完成

### S1: 预测闭环
- `scripts/prediction_daily.py` — 每日定时预测调度（ForwardPicksDB + track_record）
- `core/benchmark_client.py` — 可复用基准 NAV 客户端（HS300/ZZ500/ZZ1000）
- `scripts/prediction_attribution.py` — 前瞻选股归因 → learning_loop
- `scripts/prediction_monthly.py` — 月度命中率报告（含分组统计）
- S1-1 + S1-3 已接入归因回写

### S2: 日频数据流
- `scripts/refresh_daily.py` — 轻量增量日频数据刷新
- `core/earnings_calendar.py` — akshare 财报日历
- `scripts/event_driver.py` — 公司事件扫描 + 过期财报检测
- `pipeline/sw_serialize.py` — last30days 舆情注入（S2-4 已在 v23 实现）

### S3: 可追溯性
- `core/claim_citation.py` — 新增 `render_jsonld_ledger()` JSON-LD 输出
- `core/signal_divergence.py` — 情绪 vs 基本面分歧检测
- `scripts/falsification_tracker.py` — 证伪条件解析 + 检查
- `export/exporter.py` — [注N] 脚注引用 → Word 上标（S3-2）

### S4: 自进化能力
- `scripts/framework_effectiveness.py` — 框架使用率/通过率统计
- `core/method_reflection.py` — 新增 `get_framework_ranking()` 动态排序（S4-2）
- `core/framework_injector.py` — 新增 `inject_framework_rationale()` 数据驱动依据（S4-3）

### S5: 工程基建
- `scripts/consolidate_data.py` — 数据层整合迁移脚本（S5-2）
- `pipeline/agent_graph.py` — 节点级 checkpoint save/load/clear（S5-3）
- `pipeline/agent_graph.py` — `PipelineContext` typed dataclass（S5-4）
- S5-1 CI/CD 待配 git remote; S5-5 已在 v23 解决

### S6: 合规与信披
- `scripts/rating_tracker.py` — 评级变动检测 + 披露模板
- `scripts/target_price_reminder.py` — 12M 目标价到期提醒
- `core/compliance_clauses.py` — 按报告类型自动附免责声明
- `scripts/sensitive_info_scan.py` — 发布前敏感信息扫描（S6-4）

### S7: 工作台与编排
- `scripts/run_reports.py` — 批次状态追踪 + 断点续跑（S7-2）
- `web/app.py` — `/workbench` 路由 + `/api/batches` 状态 API（S7-1）
- `web/app.py` — `/api/review/{job_id}/approve|reject` 人工审核（S7-4）
- `scripts/cost_panel.py` — LLM 成本审计面板

---

# 1号分析师 V51 — 从 V24 到 V51 的完整演化

> ⚠️ 归档说明（2026-08-24）：本文件是**前代项目「1号分析师」**的演化史（止于 2026-07-23），
> 与本项目「二号分析师(2hao-analyst)」的关系未在文中交代。当前版本的变更请以 git 提交历史为准。

## V24 (2026-06-28) — 初始 MVP

**规模**: 5,204 行 / 36 Python 文件  
**架构**: 管线(Search→Generate→Verify) + 质量门禁(v24/v25/v26)  
**能力**: 6 个 agent prompt、3 个 JSON schema、10 个报告模板  
**状态**: 功能性 MVP，纯 LLM 管线

## V30 (2026-07-08) — 工程化

**规模**: 22,421 行 / 71 Python 文件  
**架构**: Layer1(Data)→Layer2(Compute)→Layer3(Generate) 三层  
**新增**: 财务计算引擎(收入桥/毛利桥/费用桥/DCF/三情景/可比/SOTP)  
**新增**: 数据管线(akshare/baostock/东财/港美)  
**新增**: Heritage 方法论模块(哈佛框架/证据阶梯/诚实边界/范式路由)  
**新增**: 37 个 Bluebook 模式文件  
**状态**: 全量工程，功能完整但架构臃肿

## V34 (2026-07-20) — 功能堆叠

**规模**: 74,057 行 / 181 Python 文件  
**新增**: 100+ 工具（质量门禁、回测、利润池、产业链等）  
**新增**: Web 服务器 + Web 应用  
**状态**: 功能超载，难以维护

## V50 (2026-07-21) — 架构重建

**规模**: 3,778 行 / 44 Python 文件  
**架构**: T0→T1→T2→T3 四层  
**核心理念**: 计算与生成分离、Karpathy Software 1.0+3.0  
**新增**: SAC 方法论文档、Style Compiler、SAC Gate、可观测性  
**问题**: 代码总量大幅缩减但覆盖率不足(计算引擎为空、exporter 只输出 .md)

## V50+ (2026-07-23 早期) — 功能补全

**变更**: T2a 从空壳变为论证引擎、Style Compiler 6→10 条  
**新增**: ComputeEngine adapter、ExportAdapter、T3_delivery  
**问题**: 过度约束导致 agent 写作模板化 — 10 条风格规则 + 填空式 SAC 指令 + 严格门禁

## V51 (2026-07-23 当前) — 回归本质

**规模**: 38 Python 文件（+29 外部 V30 资源）  
**架构**: core/data/compute/export 四目录，按功能命名不按层编号

### 核心变更

| 变更 | V50+ | V51 |
|------|------|-----|
| Style Compiler | 10 条规则（过度收敛） | 3 条规则（去套话/结论先行/密度告警） |
| SAC 指令 | "判断一/二/三"填空模板 | "格式自由，覆盖维度即可" |
| 批判循环 | 无（一次性流水线） | Devil's Advocate 自审+修改 |
| 质量基准 | 测试只测编译通过 | 回归测试对标 V22 真实报告 |
| AI 标注 | AIGC 元数据+"内容由AI生成" | 代码层+指令层禁止 |
| 回测系统 | 无 | FinRpt 5 维评分管线 |
| 目录结构 | T0-T3 编号层 | core/data/compute/export 功能名 |

### 设计哲学

**三条铁律**：
1. 报告必须像人写的 — 无 AI 标注、无方法论标签、无免责声明
2. 计算层不参与生成，生成层不参与计算 — 确定性 Python 代码不装 LLM
3. 方法论文档是可验证的执行契约 — SAC(YAML) 被代码检查，LLM 不能绕过

**约束的黄金密度**：不超过 3 条硬规则。后置检查只检查"不可编造的事"，不检查风格偏好。
