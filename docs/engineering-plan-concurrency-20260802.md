# 2号分析师 综合工程方案（2026-08-02）

> 整合：系统现状全景 + 网上顶级打法调研 + 用户决策（Marvis优先/DeepSeek兜底）
> 目标：把 2hao 从"能生成、经得起单次检查"推向"多报告并发稳定、数据不可写错、LLM 路由智能"

---

## 一、系统现状全景

### 1.1 管线架构（已固化）

```
scheduler → E2EOrchestratorV2 → data_collect → enrich → compute → charts
         → section_writer(维度并行) → IronGate(50+检查) → export(md/docx/pdf/pptx)
```

### 1.2 各层能力盘点（R24-R46 成果）

| 层 | 已有能力 | 已知短板 |
|---|---|---|
| **数据层** | R37 补采（financials.db 535万行/99.2%覆盖）；R39 统一提取层；R36 产业链 69 行业 | 净利口径冲突（3.41 vs 1.68 亿）；美股缺字段 |
| **生成层** | R35 数值纪律；R39 数据契约；R38 图注残留清理 | 图注仍可能硬编码绕过数据源 |
| **校验层** | R35 算术校验；R38 财务一致性；R45 双字连接词；R46 不变量断言 | Gate 仍测"长什么样"多于"对不对" |
| **渲染层** | R40 空段/图表目检；R42 静态目录+拟人化；R43 目录完整 | 图表仍集中附录 |
| **LLM 层** | R13 三算力架构；provider 熔断；Marvis 队列 | 静态优先级；无超时；无并发限流 |
| **编排层** | scheduler 单条跑 | 多报告并发无队列/无锁/无优先级 |

### 1.3 核心痛点（用户反馈 + 圆桌审计）

1. **多报告并发堵塞**：多个报告同时跑，抢 SQLite 写锁 + 单 DeepSeek API + 共享文件
2. **LLM 路由僵化**：Marvis 优先是静态的，Marvis 拥塞时仍走它，DeepSeek 空闲却不用
3. **数据可写错**：图注/补丁脚本可绕过数据源（净利 3.41 幻觉）
4. **Gate 结构性**：高分掩盖数据错误（0.9487 全绿含 5 类硬伤）

---

## 二、网上顶级打法调研

### 2.1 LLM 路由/网关

| 方案 | 核心思想 | 来源 |
|---|---|---|
| **LiteLLM / Portkey / Kong AI Gateway** | 统一网关：多 provider 动态路由、key 管理、成本追踪、fallback 链 | [Spheron](https://www.spheron.network/blog/ai-gateway-litellm-portkey-kong-gpu-cloud/)、[Morph](https://www.morphllm.com/llm-proxy) |
| **延迟感知自适应路由** | provider 选择考虑 p50/p95 延迟，而非静态优先级 | [pydantic-ai issue](https://github.com/pydantic/pydantic-ai/issues/5160) |
| **Hybrid 云+本地分层** | 机械任务走本地，复杂任务走云端 | [SitePoint](https://www.sitepoint.com/hybrid-cloudlocal-llm-the-complete-architecture-guide-2026/) |
| **模型路由器网关** | 请求级路由：类型→模型映射 + 熔断 + 重试 | [engineering-handbook](https://github.com/handbook-academy/engineering-handbook/blob/main/content/hld/part-8-case-studies/37-model-router-gateway.md) |

### 2.2 SQLite 并发

| 方案 | 核心思想 | 来源 |
|---|---|---|
| **WAL + busy_timeout** | 读写并行、写写排队，busy_timeout 等待而非报错 | [cashubtc](https://github.com/cashubtc/nutshell/issues/907)、[hermes-agent](https://github.com/NousResearch/hermes-agent/pull/3385) |
| **写锁预防升级** | 提前暴露读写竞争，避免事务升级死锁 | [SQLite Forum](https://www2.sqlite.org/forum/forumpost/b58aa87fe1195280) |
| **批量提交优化** | 高频写合并为批处理，减少锁竞争 | [腾讯云](https://cloud.tencent.cn/developer/ask/2208402/answer/2950163) |

### 2.3 任务编排

| 方案 | 核心思想 | 来源 |
|---|---|---|
| **Prefect task runners** | Flow/Task 分解，并发执行 + 重试 | [Prefect](https://theneuralbase.com/prefect/learn/intermediate/parallel-task-execution/) |
| **Prefect vs Celery** | 轻量 DAG vs 分布式队列 | [对比](http://mp.weixin.qq.com/s?__biz=MzYzMjE5MDkwOA==&mid=2247485178&idx=1&sn=6a4b1f02d361f904dd0c35d959c7eaed) |
| **worker 池 + 并发上限** | 任务进队列，N 个 worker 消费，背压控制 | [TheNeuralBase](https://theneuralbase.com/prefect/learn/intermediate/performance-tuning/) |

### 2.4 数据完整性/幻觉防护

| 方案 | 核心思想 | 来源 |
|---|---|---|
| **Neuro-Symbolic 验证** | LLM 输出过符号引擎校验（数值/逻辑） | [arXiv](https://arxiv.org/abs/2605.26942) |
| **Aegis-DQ** | agentic 数据质量框架：字段非空/口径/范围断言 | [aegis-dq](https://github.com/aegis-dq/aegis-dq) |
| **零错误 RAG** | 财务工作流：数值必须来自检索源，禁自由生成 | [Henon](https://www.advfn.com/stock-market/stock-news/97580413/world-first-henon-launches-zero-error-rag-system) |
| **加密验证** | 对关键输出做可验证哈希，防篡改 | [dev.to](https://dev.to/myselfadityadav/the-12-billion-blindspot-architecting-sub-12ms-cryptographic-verification-to-prevent-ai-2gnf) |

### 2.5 报告渲染/文档管线

| 方案 | 核心思想 | 来源 |
|---|---|---|
| **确定性 office-gate + 渲染验证** | 文档生成后自动渲染验证（OfficeCLI） | [superoffice-skills](https://github.com/cskwork/superoffice-skills) |
| **导出管线规范化** | md→docx 全链路 + 目检闭环 | [yao-crux](https://github.com/yaojingang/yao-open-skills/blob/main/skills/yao-crux-skill/references/report-export-pipeline.md) |

---

## 三、最优方案（综合判定）

### 总体架构：分层解耦 + 每层一个顶级打法

```
┌─────────────────────────────────────────────────────┐
│  编排层：报告任务队列（Prefect 思想）+ 并发上限 + 优先级   │
├─────────────────────────────────────────────────────┤
│  LLM 层：LlmRouter 动态路由（LiteLLM 思想）             │
│   健康度加权 + 超时回退 + 并发信号量 + 任务分层           │
├─────────────────────────────────────────────────────┤
│  数据层：统一连接 + WAL + 写锁（SQLite 最佳实践）         │
│   数据口径契约（单一事实源）                            │
├─────────────────────────────────────────────────────┤
│  校验层：不变量断言 + 数据一致性（Neuro-Symbolic）        │
├─────────────────────────────────────────────────────┤
│  渲染层：数据驱动图注 + 目录/空段目检（office-gate）      │
└─────────────────────────────────────────────────────┘
```

### 3.1 编排层：报告任务队列（最高优先解决"多报告并发堵塞"）

**方案**：`queue.Queue` + N 个 worker + 优先级 + 并发上限

```
scheduler("A") ─┐
scheduler("B") ─┼→ ReportQueue → Worker1 → 跑 A 管线
scheduler("C") ─┘   (优先级)     Worker2 → 跑 B 管线
                                Worker3 → 跑 C 管线
并发上限: 2（防 SQLite/API 争抢）
```

- **优先级**：大报告（listed）高优先级，快报告（earnings_notes）低
- **背压**：队列满时新请求等待，不无限并发
- **实现**：`scripts/run_reports.py` 支持 `["A","B","C"] --workers 2`

### 3.2 LLM 层：动态路由（解决"Marvis 僵化"）

**方案**：`LlmRouter` 替换静态优先级，四个能力：

```
1. 动态健康度 = base_priority + 实时惩罚
   Marvis 空闲 → 最高优先（免费 token 最大化）
   Marvis 拥塞/失败 → DeepSeek 顶上（不阻塞）

2. 超时回退：每个 provider 调用 TTL
   Marvis 队列入队 30s 未响应 → 回退 DeepSeek

3. 并发信号量：Semaphore(2) 控制每 provider 并发

4. 任务分层路由：
   起草/扩写（token 密集）→ Marvis 优先
   关键判断/编辑合并（质量敏感）→ DeepSeek 优先
   评分/格式检查（机械）→ 本地 Ollama（零成本）
```

### 3.3 数据层：统一连接 + 数据契约（解决"SQLite 锁 + 口径冲突"）

**方案**：
```
1. get_connection() 单例 + WAL + busy_timeout(30s)
   → 所有 sqlite3.connect 收敛到 data_backends.py

2. 单写者模式：写入收敛到 save_rows，加 threading.Lock

3. 数据口径契约：每个关键字段标注口径
   netProfit → {"归母净利": 1.68, "含少数股东": 3.41}
   报告必须引用归母口径（与 enrich 一致）
```

### 3.4 校验层：不变量断言 + 数据一致性（延续 R46）

**方案**：
```
1. 不变量断言层（已实现 R46）：市值/股本/PE/持股勾稽
2. 数据一致性：报告数字 vs data_dict 单源校验（R38）
3. 增加"图注数值校验"：图注数字必须来自 data_dict，禁手写
```

### 3.5 渲染层：数据驱动图注 + 目检闭环（延续 R40-R43）

**方案**：
```
1. 图注改 Jinja2 模板渲染：{revenue_2025} / {net_profit_2025}
   从 enrich data_dict 取数，禁手写字符串（根治净利幻觉）
2. 渲染层目检（R40 已建）：空段/分页/图表分布 + 目录渲染
```

---

## 四、实施路线图（分 3 期）

### 第一期（P0，本周）：多报告并发 + LLM 路由

| # | 任务 | 改动 | 验收 |
|---|------|------|------|
| 1 | 统一 SQLite 连接 + WAL + 写锁 | `core/data_backends.py` 重构 | 两报告并发无 `database is locked` |
| 2 | LlmRouter 动态路由 | `core/deepseek_client.py` 扩展 | Marvis 拥塞时自动切 DeepSeek |
| 3 | 报告任务队列 | `scripts/run_reports.py` | 3 报告 `--workers 2` 并行跑 |

### 第二期（P1，下周）：数据契约 + 图注数据驱动

| # | 任务 | 改动 | 验收 |
|---|------|------|------|
| 4 | 净利口径契约 | data_dict 标注归母/含少数 | 报告引用 1.68 归母 |
| 5 | 图注模板渲染 | section_writer 图注生成 | 净利 3.41 幻觉根除 |
| 6 | 美股字段补全 | us_stocks.db +pb/roe/margin | 全球对标增强 |

### 第三期（P2，后续）：质量门禁 + 编排增强

| # | 任务 | 改动 | 验收 |
|---|------|------|------|
| 7 | Gate 图注数值校验 | iron_gate 扩展 | 图注与 data_dict 一致 |
| 8 | Prefect 化编排 | 报告 DAG 化 | 重试/依赖/并发可配 |

---

## 五、关键决策记录

1. **Marvis 优先不改为 DeepSeek 优先**——保留"免费 token 最大化"决策，但改为**动态优先**（Marvis 健康时优先）
2. **不引入 Redis/Celery**——2hao 单机规模，`queue.Queue` + 进程池足够；Prefect 作为远期可选
3. **SQLite 不换 PostgreSQL**——数据量可控，WAL + 写锁足够；换库成本高收益低
4. **Gate 不放松**——不变量断言只增不减，杜绝"高分掩盖错误"

---

## 六、风险与回滚

| 风险 | 缓解 |
|------|------|
| LlmRouter 引入 bug 影响所有报告 | 默认回退到现有静态路由；A/B 测试 |
| 队列 worker 崩溃 | worker 异常隔离，重试 3 次 |
| WAL 改动影响既有 db | 逐库启用，先 financials.db 验证 |
| 数据契约改动影响下游 | 字段向后兼容，旧 key 保留 |

---

*方案基于系统现状 + 顶级打法调研（见二节来源），分 3 期可落地。*
