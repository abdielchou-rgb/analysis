# 二号分析师 (Analyst No.2)

**意图驱动的智能分析系统** — 从"机构报告生成器"升级为"回答委托方必答问题的深度报告引擎"。

2hao 把投行/咨询/审计的方法论（问题树、金字塔、假设驱动、专业怀疑）工程化为可复用的 AI 分析系统。它不只生成报告，而是**回答决策问题**。

---

## 核心能力

### 双路径执行（FP8 光谱架构）

| 路径 | 适用 | 架构 |
|------|------|------|
| **确定性管线** | 批量/标准化报告 | E2EOrchestratorV2 + SAC + IronGate |
| **工作台混合** | 单份深度/个性化 | 数据层 + Claude 直接写 + 用户审核 |

自动路由：`core/task_router.py` 按任务性质（报告类型/意图强度/风险等级/批量）选路径。高险决策文档（decision_memo）→ 工作台 + 强制人类门禁 + 双向溯源。

### 意图驱动（FP0 第一公民）

- `core/intent_parser.py`：委托方问题清单 → 必答问题 → 报告结构
- `core/intent_gate.py`：必答问题是否被报告回答（结构正确但没答对题 = 未通过）
- `core/context_compiler.py`：意图/数据/计算/约束/示例 五段程序化组装（轻量 DSPy 式）

### 计算模块（代码算，AI 只引用）

| 模块 | 能力 |
|------|------|
| `compute/contract_manufacturing.py` | 代工/合作生产测算：盈亏平衡/回收期/战略期权 |
| `compute/unlisted_deep.py` | 非上市深化：可比融资/治理/退出路径/里程碑 |
| `compute/valuation/` | DCF/可比/情景/SOTP |
| `compute/financial/` | 三表勾稽/桥接/Damodaran ERP |
| `fact_base.py` | 行业事实库（分级+纠偏+检索） |

### 三通道供能 + 节点级路由

| 通道 | 角色 | 职责 |
|------|------|------|
| DeepSeek | P0 主力 | 关键链（写作/合并/修订/终审） |
| OpenRouter | P1 兜底+圆桌 | 降级 / 异源终审 |
| Marvis | P2 免费预取 | 后台候选草稿（失败即弃） |

`route_policy.py`：perf/train 双模式节点级路由（合并组装永远走付费 DeepSeek，质量红线）。

### 质量保障

- **IronGate**：101 项注册检查（以 `pipeline/iron_gate.py` 注册表为唯一事实源，实时数量见 `docs/PIPELINE_FACTS.md`）+ 意图符合性门禁
- **专业怀疑**：写手默认假设数据可能有错（四大审计姿态）
- **异源圆桌**：OpenRouter 异源模型终审 + 信誉加权（评审不担责 → 信誉分）
- **语义早停**：修订收敛即停（省 38% token）
- **门禁熔断**：同一失败项 N 次降级重写（防死锁）

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
playwright install --with-deps  # 可选：网页抓取

# 2. 配置 API 密钥（复制 .env.example → .env）
cp .env.example .env
# 填 DEEPSEEK_API_KEY（必须）+ OPENROUTER_API_KEY（推荐）

# 3a. 批量标准报告 → 管线
python pipeline/scheduler.py "芯联集成" --type listed_company

# 3b. 高险决策备忘录 → 工作台混合（意图驱动）
python -m core.workbench_executor "柯力传感" --type decision_memo \
    --requirement "久通把油位传感器业务给柯力生产，评估市场规模/投入产出比/战略卡位/衍生价值" \
    --human-gate

# 3c. 或先查任务该走哪条路径
python -c "from core.task_router import route_task; print(route_task('decision_memo', '评估投入产出'))"
```

### 数据不足时（桥接节点，第〇原则）

```bash
# ① 快速检查缺口（不写报告）
python pipeline/scheduler.py "标的" --type listed_company --data-check-only
# ② 生成 enrich 模板，补数据（每条带 source）
python scripts/agent_backfill.py template "标的" --out enrich.json
# ③ 回流管线
python pipeline/scheduler.py "标的" --type listed_company --enrich-file enrich.json
```

---

## 环境变量

见 [.env.example](.env.example)。关键项：
- `DEEPSEEK_API_KEY`（必须）、`OPENROUTER_API_KEY`（推荐）
- `RUN_MODE`：perf / train
- `CUSTOM_REQUIREMENT`：柔性定制需求
- `MAX_ATTEMPTS` / `EARLY_STOP_SIMILARITY` / `REPAIR_CIRCUIT_BREAK`：修订收敛控制

---

## 架构总览

```
┌─ 任务路由器（core/task_router.py）──────────────┐
│  批量 → 管线（E2E+SAC+IronGate）                  │
│  深度 → 工作台（intent_parser → context_compiler）│
│  高险 → 工作台+人类门禁+双向溯源                    │
└──────────────────────────────────────────────┘
        │ 共享底层
        ▼
┌─ 数据层 ──────────────────────────────────────┐
│  akshare / enrich / 决策引擎 / 财务模型 / R87分级 │
├─ 校验层 ──────────────────────────────────────┤
│  verify_report（算术/实体/一致性）+ intent_gate  │
├─ 记忆层 ──────────────────────────────────────┤
│  learning_loop + fact_base + 纠偏规则            │
└──────────────────────────────────────────────┘
```

### 目录结构

```
core/
  intent_parser.py / intent_gate.py     意图层（FP0）
  task_router.py / workbench_executor.py 光谱架构（FP8）
  context_compiler.py                   上下文模板程序化
  fact_base.py                          行业事实库
  compute/contract_manufacturing.py     代工测算
  compute/unlisted_deep.py              非上市深化
  compute/valuation/ financial/         估值/财务
  frameworks/*.yaml                     方法论框架（15个）
  sacs/sac_decision_memo.yaml           SAC 意图映射
pipeline/
  e2e_orchestrator.py / route_policy.py 管线+路由
  section_writer.py / iron_gate.py      写作+门禁
scripts/
  run_reports.py / agent_backfill.py    编排+兜底
```

---

## 最近更新 (2026-09-03)

### 质量门 & 鲁棒性

| 功能 | 文件 | 说明 |
|------|------|------|
| A1: Gate fail-closed | `pipeline/checks/base.py` | 空 error checks → 阻断，不放行 |
| A2: judge_ver versioning | `pipeline/checks/base.py` | GateReport 含版本号+配置哈希 |
| B1: placeholder protocol | `pipeline/e2e_orchestrator.py` | `{{tp_primary}}` 自动填充+残余检测 |
| D1+D2: node contract | `pipeline/e2e_orchestrator.py` | 节点完成合约：空字段→整链失败 |
| D3: retry by error class | `core/retry_policy.py` | 错误分类（速率限制/超时/未知）→不同重试策略 |
| D4: 幂等台账 | `core/idempotent_ledger.py` | 侧效应先写 pending→执行→标记 done，崩溃恢复 |
| D5: HITL durable | `core/hitl_durable.py` | 审批请求持久化，崩溃后可续跑 |
| D6: fault injection tests | `tests/test_fault_injection.py` | 故障注入：验证 fail-closed 行为 |

### 效度 & 校准

| 功能 | 文件 | 说明 |
|------|------|------|
| C1: calibration panel | `core/calibration/` | 校准面板：按置信度段/Brier score |
| C2: posterior recalibration | `core/calibration/` | 事后重校准：系统性偏差自动修正 |
| C3: MC significance | `core/significance.py` | N=1000 随机模拟，报告 p-value |
| C4: live-forward cohort | `core/cohort.py` | 按 made_date 冻结，到期日取数，防止幸存者偏差 |
| C5: dimension attribution | `core/attribution.py` | 维度/框架归因：IC + hit rate 分析 |
| C6: prediction timeline | `core/prediction_timeline.py` | 预测更新事件记录+时间线 |

### 集成 & 可观测

| 功能 | 文件 | 说明 |
|------|------|------|
| integration tests | `tests/test_integration.py` | 20 个端到端测试覆盖全部新功能 |
| summary dashboard | `core/dashboard.py` | 一键汇总：校准+显著性+归因+队列 |
| CI import checks | `.github/workflows/ci.yml` | 13 个模块导入验证 |

---

## 质量保证体系

| 层级 | 机制 | 触发 |
|------|------|------|
| L0 | 语法 + import 链 | CI |
| L1 | 意图符合性（intent_gate） | validate 节点 |
| L2 | IronGate 101 项注册检查（实时数见 PIPELINE_FACTS） | 导出前 |
| L3 | StyleCompiler（去 AI 化） | 写作后 |
| L4 | 异源圆桌 + 信誉加权 | 终审 |
| L5 | 成本日志（cost_audit） | 全程 |

---

## 文档体系

| 文件 | 内容 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | AI Agent 行为约束宪法（含 FP0 意图第一） |
| [AGENTS.md](AGENTS.md) | 开发者配置与架构 |
| `docs/FP1-FP7-超级智能法则.md` | 顶层宪法 |
| `docs/CLAUDE-architecture.md` | 运维手册 |
| [.env.example](.env.example) | 环境变量模板 |

---

## 路线图

- [x] P0：意图层 + 代工测算 + FP0 入宪
- [x] P1：任务路由 + 工作台 + 咨询框架 + 专业怀疑
- [x] P2：事实库 + 非上市深化 + 深度接线
- [x] P3：SAC 意图重构 + 上下文编译 + 端到端验证
- [ ] DSPy 编译式上下文全自动优化
- [ ] 非上市尽调全量深化

---

*License: MIT*
