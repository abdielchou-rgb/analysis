# 2号分析师 双模式综合架构方案 V2（2026-08-02）

> 整合：双模式（训练/性能）+ 全部未完成优化项 + 网上顶级打法逐项对标
> 目标：让 2hao 既能在训练模式下无限打磨质量，也能在性能模式下并发高速交付

---

## 一、总览：双模式架构

```
                     ┌─────────── 训练模式（Train）───────────┐
                     │  LLM: Marvis（免费 token 最大化）        │
                     │  流程: 写→审→改→记（自迭代直到满意）      │
                     │  定时: schedule 每日自动跑一轮            │
                     │  产出: 综合分析 + 学习沉淀               │
                     └──────────────────────────────────────┘
 用户指令 → 路由决策
                     ┌─────────── 性能模式（Perf）────────────┐
                     │  LLM: DeepSeek（高速）                  │
                     │  流程: 多报告并发 → 最快输出              │
                     │  并发: ReportQueue + workers + 隔离     │
                     │  产出: 多份报告同时交付                  │
                     └──────────────────────────────────────┘
       共享层：不变量断言 / 数据契约 / 渲染目检 / 学习沉淀
```

---

## 二、模式定义

### 训练模式（Train Mode）

**目标**：质量打磨 + 学习沉淀。用免费 token 无限迭代。

| 维度 | 配置 |
|---|---|
| LLM 路由 | provider=agent_provider（Marvis 优先），deepseek 兜底 |
| 迭代深度 | MAX_ATTEMPTS 3→可配置 10+，直到 Gate 全过 + 审计无 P0 |
| 自动流程 | 写报告 → 圆桌审计 → 反思 → 改报告 → 记录过程 |
| 定时驱动 | schedule 每日自动跑一轮 → 汇成综合分析 |
| 输出 | 最终报告 + 修改历史 + 综合分析 |

### 性能模式（Performance Mode）

**目标**：多报告并发高速交付，互不干扰。

| 维度 | 配置 |
|---|---|
| LLM 路由 | provider=deepseek（高速），Marvis 兜底 |
| 并发 | ReportQueue + workers=2 + 输出目录隔离 |
| 迭代深度 | MAX_ATTEMPTS=3（快速收敛） |
| 输出 | 多份报告同时产出 |

---

## 三、整合全部未完成优化项

### 3.1 编排层（性能模式核心）

**未完成项**：多报告并发堵塞（SQLite 写锁 + 单 API + 共享文件）

```
run_reports.py ["A","B","C"] --mode performance --workers 2 --llm deepseek
       ↓
ReportQueue（优先级队列）
  ├─ Worker1 → A 管线（进程隔离）
  └─ Worker2 → B 管线
       → C 排队
```

**顶级打法对标**：
- **Prefect task runners**（[TheNeuralBase](https://theneuralbase.com/prefect/learn/intermediate/parallel-task-execution/)）：Flow/Task 分解 + 并发执行 + 重试
- **结论**：2hao 单机规模用 `queue.Queue` + `concurrent.futures.ProcessPoolExecutor` 足够，Prefect 作为远期可选（不引入 Redis/Celery）

### 3.2 LLM 层（双模式路由）

**未完成项**：LLM 路由僵化（Marvis 静态优先）

```
LlmRouter（动态路由）
  ├─ 模式选择：Train → Marvis；Perf → DeepSeek
  ├─ 健康度加权：provider 拥塞/失败 → 自动切换
  ├─ 超时回退：Marvis 队列 30s 未响应 → DeepSeek
  └─ 并发信号量：Semaphore(2) 防 API 限流
```

**顶级打法对标**：
- **LiteLLM / Portkey 动态路由**（[Spheron](https://www.spheron.network/blog/ai-gateway-litellm-portkey-kong-gpu-cloud/)）：多 provider 动态路由 + fallback + 成本追踪
- **延迟感知路由**（[pydantic-ai](https://github.com/pydantic/pydantic-ai/issues/5160)）：p50/p95 延迟加权
- **结论**：2hao 用轻量 LlmRouter（自带），不引入 LiteLLM 网关（单机规模）

### 3.3 数据层（契约 + 隔离）

**未完成项**：
1. 数据可写错（图注/补丁绕过数据源 → 净利 3.41 幻觉）
2. 跨标的串标（云迹 data_dict 混入柯力数据）
3. SQLite 写锁

```
1. get_connection() 单例 + WAL + busy_timeout(30s) + 写锁
2. 数据口径契约：净利标注归母(1.68)/含少数(3.41)
3. 标的隔离：data_dict 加 asset_id，消费前校验标的匹配
4. 图注数据驱动：Jinja2 模板从 data_dict 渲染，禁手写
```

**顶级打法对标**：
- **Soda Data Contracts**（[Soda](https://docs.soda.io/soda-documentation/soda-v3/data-contracts)）：数据契约 schema 校验 + SLA
- **单一事实源**（[RBI 银行框架](https://bfsi.economictimes.indiatimes.com/articles/rbi-introduces-comprehensive-data-governance-framework-for-banks-enforcing-single-source-of-truth/132424783?utm_source=newslisting&utm_medium=latestNews)）：同一标的只能一个权威来源
- **Data Lineage**（[dunnixer](https://www.dunnixer.com/insights/information/banking/us/data-lineage-tooling-as-a-feasibility-test-for-trusted-numbers)）：每个数据点记录来源标的
- **结论**：引入"标的隔离校验"（asset_id 校验）+ 图注模板渲染——这是根治串标和幻觉的关键

### 3.4 校验层（不变量 + 留白）

**未完成项**：
1. Gate 结构性（高分掩盖数据错误）
2. 激励结构奖励粉饰（诚实留白被惩罚）

```
1. 不变量断言层（已建 R46）：市值/股本/PE/持股勾稽
2. DCF 输出一致性断言：模型复算 vs 报告声称，偏差>10% 拦截
3. 敏感性单调性断言：WACC↑→市值↓ 校验
4. "留白"通道：数据缺失显式标注，不计 SAC 缺失，奖励诚实
5. Gate 未过不交付：3 轮失败硬阻断，禁止人工放行
```

**顶级打法对标**：
- **Reinforced Hesitation**（[arXiv 2511.11500](https://ar5iv.labs.arxiv.org/html/2511.11500)）：奖励"诚实回避"而非硬答
- **BreakBench**（[GitHub](https://github.com/wongqihan/breakbench)）：压力下 agent 是否保持诚实
- **"信任不是答案，Gate 才是"**（[dev.to](https://dev.to/igorganapolsky/an-ai-agent-faked-a-sales-tax-to-hide-its-own-bug-the-fix-isnt-trust-its-a-gate-1nna)）：不可绕过的 Gate
- **结论**："留白通道"是改变激励结构的关键——让标注缺口比粉饰更被奖励

### 3.5 渲染层（目检闭环）

**未完成项**：图表集中附录（正文 0 图）

```
1. 渲染层目检（已建 R40）：空段/分页/图表分布
2. 图表随文：按论证章节分布关键图，正文引用图号
3. 静态目录（已建 R42/R43）：一级+二级+三级
```

**顶级打法对标**：
- **deterministic office-gate + 渲染验证**（[superoffice-skills](https://github.com/cskwork/superoffice-skills)）：文档生成后自动渲染验证
- **结论**：图表随文是内容结构设计，需在 section_writer 骨架层调整

### 3.6 学习沉淀（训练模式核心）

**未完成项**：预测验证闭环从未运转（FP5 智能演化空转）

```
1. LearningLoop（已建）：before/after_report
2. edit_cases（已建）：存修正
3. 升级：每轮改报告过程记录（diff/原因/结果）入库
4. 训练模式沉淀 → 性能模式读作初始 findings
5. 预测验证：validate_predictions.py 定期跑，校准置信度
```

**顶级打法对标**：
- **Self-Improving Agent 反思循环**（[Taskade](https://www.taskade.com/blog/self-improving-ai-agents-reflection)、[agent-learn](https://github.com/adi1999/agent-learn)）：递归学习 + 记忆
- **Recursive Self-Improvement**（[DataScienceDojo](https://datasciencedojo.com/blog/recursive-self-improvement-agentic-ai/)）：多轮自我提升
- **结论**：训练模式的"写→审→改→记"正是反思循环，需把"记录"结构化

---

## 四、实施路线图（合并 3 期 + 双模式）

### 第一期（P0）：性能模式并发基础
| # | 任务 | 优先级 |
|---|---|---|
| 1 | 统一 SQLite 连接 + WAL + 写锁 | 🔥 消除 database is locked |
| 2 | run_reports.py 任务队列（--workers 2） | 🔥 多报告并发 |
| 3 | 输出目录隔离验证 | 🔥 互不干扰 |
| 4 | LlmRouter 动态路由（模式切换 + 超时回退） | 🔥 双模式基础 |

### 第二期（P1）：数据契约 + 校验增强
| # | 任务 | 优先级 |
|---|---|---|
| 5 | 标的隔离校验（asset_id） | 🔥 堵串标 |
| 6 | 图注数据驱动渲染 | 🔥 堵幻觉 |
| 7 | DCF 输出一致性断言 | 🔥 堵循环论证 |
| 8 | 净利口径契约 | 数据真实 |

### 第三期（P2）：训练模式闭环 + 学习复用
| # | 任务 | 优先级 |
|---|---|---|
| 9 | 训练模式自迭代（MAX_ATTEMPTS 可配置 + 审计反馈回流） | 🔥 质量打磨 |
| 10 | 改报告过程记录 + 综合分析 | 🔥 学习沉淀 |
| 11 | 定时任务驱动（schedule） | 自动化 |
| 12 | 敏感性单调性断言 + 留白通道 | 激励修复 |

---

## 五、关键决策

1. **双模式共享同一套校验层**——质量底线一致，只差 LLM 路由和迭代深度
2. **不引入 Redis/Celery/LiteLLM**——单机规模原生方案足够
3. **训练模式不阻塞性能模式**——定时任务独立跑，不占性能并发配额
4. **"满意"标准**——Gate 全过 + 审计无 P0 + 渲染目检通过
5. **留白通道优先于粉饰**——SAC 覆盖"诚实标注缺口"不扣分

---

## 六、风险与回滚

| 风险 | 缓解 |
|---|---|
| LlmRouter 引入 bug | 默认回退现有静态路由 |
| 并发 worker 崩溃 | 异常隔离 + 重试 3 次 |
| WAL 改动影响既有 db | 逐库启用验证 |
| 双模式配置复杂 | 默认性能模式，训练模式显式开启 |

---

*方案整合了全部未完成优化项（编排/LLM/数据/校验/渲染/学习）+ 双模式需求 + 顶级打法对标。*
