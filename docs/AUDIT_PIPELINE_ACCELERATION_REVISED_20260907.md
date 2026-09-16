# 管线加速修正版 · Ultra-think 深度审计

> 日期：2026-09-07
> 审计对象：`docs/PIPELINE_ACCELERATION_REVISED_20260907.md`（下称"修正版"）
> 对照物：`docs/PIPELINE_ACCELERATION_ANALYSIS_20260907.md`（原方案）、`docs/PROFILE_BOTTLENECK_ANALYSIS_20260907.md`（424 行 PROFILE 原始分析）
> 方法：文档主张逐条回到代码验证（含接线、默认值、依赖拓扑、消费链），不做代码改动

---

## 一、总评（结论先行）

**修正版是本仓库迄今最诚实的一份性能路线图**：它用真实 PROFILE 推翻了自己上一版"教科书式加速"里的伪优化（charts 预热、全局 asyncio、provider 预探测、全局响应缓存），且把已落地的 P0-1/P0-2 如实标为"已完成"，没有邀功。逐条代码核验后，其事实性主张**绝大多数成立**，优先级重排（两个 LLM 大节点 + 重尾极值 > 图表/并行/缓存）方向正确。

但在超深度审查下，修正版仍有三层盲区：

1. **低估了 P0-1 熔断后的"僵尸 LLM 线程"问题**——45s 预算只让主流程脱身，已发出的慢调用在线程池后台继续重试，仍占用 provider 吞吐与限流额度，且可能与紧随其后的 write_sections 并发组写作叠加、加剧 429。
2. **把"观测"当成了"修复"**——P0-2 只加了段级耗时日志（正确且必要），但修正版没有给出"拿到最慢组之后干什么"的第二刀：merge 串行 LLM、gate 失败→全组重写、组内 LLM 单次 180s HTTP 超时，这三者在代码里都是比"最慢组是谁"更具体的候选刀口。
3. **对重尾归因过粗**——data/validate/record_results 的重尾（p90 96s、max 5-13min）大概率不是网络/LLM，而是节点内某段重试/自愈/共享锁的二次放大；修正版只给"全局墙钟预算"这一个锤子，没有先做节点内分段时间（validate 内部 Gate 各检查项的耗时）就下手。

一句话：修正版**修正方向对、事实基本准、但手术刀不够细**。它正确回答了"砍哪里"，尚未回答"每一刀砍多深、怎么防复燃、失败阈值怎么设"。

---

## 二、修正版主张逐条核验结果（含代码锚点）

| 主张 | 核验结果 | 代码锚点 |
|---|---|---|
| P0-1 已落地：`question_tree_v2` 带共享预算，超预算回落模板，`pool.shutdown(wait=False)` | ✅ 属实。默认 45s，`max(5.0, …)` 兜底，settings 可配 `RESEARCH_LLM_BUDGET_S` | [research_planner.py:128-218](D:/Claude/projects/2hao-analyst/pipeline/research_planner.py:128) |
| P0-1 收益叙述"155s → ~45s 上限" | ✅ 有代码支撑，但有前提（见第三节"僵尸线程"） | [research_planner.py:161-218](D:/Claude/projects/2hao-analyst/pipeline/research_planner.py:161) |
| P0-2 已落地：组级 + merge 级耗时日志、≥30s 慢组告警、merge ≥15s 告警 | ✅ 属实，组级 profile 在 as_completed 汇总后输出，merge 单独计时 | [section_writer.py:2841-2900](D:/Claude/projects/2hao-analyst/pipeline/section_writer.py:2841)、[section_writer.py:3125](D:/Claude/projects/2hao-analyst/pipeline/section_writer.py:3125) |
| 原方案"风险零"低估（asyncio/预探测/DAG 改依赖） | ✅ 判断正确。代码里节点超时是 `future.result(timeout)`，线程不可杀，asyncio 也改变不了"调用次数" | [agent_graph.py:199-213](D:/Claude/projects/2hao-analyst/pipeline/agent_graph.py:199) |
| 原方案"全局缓存"危险 | ✅ 判断正确。`deepseek_client` 缓存注释明确修订循环依赖轮间采样差异 | [deepseek_client.py:352](D:/Claude/projects/2hao-analyst/core/deepseek_client.py:352) |
| research_planner 155s 在关键路径上、不是旁路 | ✅ 属实且常被忽略：`write_sections` 的 deps 显式包含 `research_planner`，拓扑上 write 必等 planner 完成；planner 产出经 `_research_questions → _inj_rp_str → rp_str → 各组 prompt` 真实进入写作，不是死代码 | [e2e_orchestrator.py:2205-2218](D:/Claude/projects/2hao-analyst/pipeline/e2e_orchestrator.py:2205)、[prompt_injectors_p3b.py:95-120](D:/Claude/projects/2hao-analyst/pipeline/prompt_injectors_p3b.py:95) |
| "write_sections 是第一稳定大头" | ⚠️ 部分成立。node 级 107s 含 merge，且自愈/重试成本未拆出（见第四节 3） | [section_writer.py:2874-2951](D:/Claude/projects/2hao-analyst/pipeline/section_writer.py:2874) |
| P1 按维度注入需等 KB 门禁稳定 | ✅ 判断正确（与 KB 落地周目结论自洽） | — |
| P2 明确不做的四项 | ✅ 与代码现状一致，且被注释/实现佐证 | [core/settings.py:69-102](D:/Claude/projects/2hao-analyst/core/settings.py:69) |

结论：**修正版的"否定清单"全部经得起代码检验，这是它最有价值的部分；修正版自己的"肯定清单"（P0-3/P0-4/P1）方向对，但落在代码上仍有几个更便宜、更精准的先手没被识别。**

---

## 三、P0-1 的残余风险：预算熔断 ≠ 调用取消（最高优先级发现）

### 3.1 机制

`question_tree_v2` 用 6 路线程池，主线程 `wait(...timeout=剩余预算)`，预算耗尽即 break 并 `pool.shutdown(wait=False, cancel_futures=True)`。

问题：**`cancel_futures` 只能取消尚未开始的 future；已经在 `_llm_generate_questions` 里发起 `requests.post(timeout=180s)` 的线程无法被中断**（Python 线程不可杀，`agent_graph.py` 注释自己承认了这一点）。

### 3.2 后果

- 45s 预算只保证**主流程** 45s 脱身；被留下的慢线程仍可能再占用 100-200s，继续消费 provider 限流窗口与队列。
- 该节点结束后，`AgentGraph` 随即进入同一层的其它节点（含后续 write_sections 的 6-8 组并发写作）。**僵尸请求与组写作并发打同一 provider**，正是原 PROFILE 里 429 连锁失败的复现温床。
- 这个开销在 `[PROFILE]` 节点耗时里**不可见**——它是"熔断后仍在燃烧但不计入任何节点"的隐性负载。

### 3.3 建议（不动代码前的确认点）

1. 给 `_llm_generate_questions` 的单次调用加**独立的短超时**（如 20-30s），让"预算耗尽"与"调用被杀"语义一致——比只靠共享预算更干净。对应位置 `deepseek_client.call_llm` 的 `timeout` 目前是全局 `llm_http_timeout()`（默认 180s）。
2. 在 `[RQ]` warning 里加**回退计数**（多少维度回落 v1 模板），并作为观测指标持久化：45s 是"健康 provider 的上限"还是"常触发的质量降级"，必须用数据回答。
3. 把 `wait=False` 线程的善后做成显式：要么并发上限 = min(6, dims) 且单调用短超时，要么规划阶段**完全去掉 LLM 问题生成**（v1 模板 + 冲突检测是确定性快路径，见第四节 1）。

---

## 四、修正版遗漏的三处代码级刀口

### 4.1 research_planner 的 LLM 问题生成该不该在关键路径（比 45s 更狠的问题）

证据链显示 planner 产出**确实被消费**（`_inj_rp_str` 注入各组 prompt），所以不能简单判死代码。但可问三个更根本的问题：

- LLM 生成的问题与 v1 模板问题对最终 Gate 分数的增量贡献有多少？无此度量，45s 就是"花在关键路径上的固定税"。
- `_write_group` 已把完整 prompt（含 research 问题）逐组注入，问题是否只对对应维度有意义？若是，动态注入天然该把"研究问题"也按组切片（目前是全量进每组）。
- planner 里 `detect_conflicts`（确定性、毫秒级）与 `hypothesis_plan`（Phase E）才是真正的价值；LLM 问题生成应可整体开关（`RESEARCH_PLANNER_LLM=0`），由 P0-4 的真实对比决定默认值。

### 4.2 单次 HTTP 超时 180s 是重尾的最直接放大器

`deepseek_client` 每个 provider 尝试超时 = `llm_http_timeout()` 默认 **180s**（openrouter 流式更被 `max(180, 300)` 抬高到 300s）；失败后还会走全量回退链再打一轮。8 组并发 × 2 次 attempt × 多 provider 回退 = write_sections 的 2502s 不需要任何"慢模型"，仅超时叠加就够。

这比"全局墙钟预算"更便宜、先手更靠前：

- 对 **research_planner / 规划类短任务**单独设 30s 超时；
- 对 **组写作**把超时从 180s 收到 60-90s 并在超时后**快速降级到备用 provider**（现有 fallback 已具备，只是超时太长）；
- 对 **merge**（串行、单次调用）单独设超时档。

### 4.3 merge 与自愈/重试成本没进修正版的收益模型

`_write_group` 全部失败后有一段**串行 SELF-HEAL**（换 provider 全组重写），再统一走 `_editor_merge`（DeepSeek 读全部组输出，超过 `EDITOR_LLM_MERGE_MAX_CHARS=50_000` 时还要分桶两段合并）。这两个都是 node 级耗时的一部分，但 P0-2 的日志只覆盖"组完成"与"merge 完成"，**没有覆盖 SELF-HEAL 耗时与重试次数**。

修正版 P0-4 若只读现有日志，会得到"某个组 40s 最慢"，但无法区分 107s 里有多少是：

- 正常组写作墙钟（≈ 最慢组）；
- 失败组的 SELF-HEAL 串行重写；
- merge 的 1-2 次 LLM 调用。

建议 P0-2 补齐 `[SELF-HEAL][PROFILE]` 耗时与失败组清单——这是"下一刀"的最小数据前提。

---

## 五、对修正版自身表述的四点纠偏（诚实性检查）

1. **"中位 262s → ~155s"的组合效果表格应改写**：P0-2 只是 instrumentation，本身不省时；P0-1 的 45s 上限在健康 provider 下成立，但没把僵尸线程与回退质量损失计入。组合效果应写成"上界收敛到 ~45s（research）+ 观测就位（write），真正的省时刀是 P0-3/P1"。
2. **PROFILE 口径需要声明**：424 行跨 10+ 运行、8-02~08-29、不同报告类型与版本聚合；write_sections 的 n=38 可能混有 attempt 多轮与不同写作路径（3 段并行 vs 维度并行）。P0-4 应明确"同一版本、同一报告类型、干净环境"复测一次，而非直接拿历史中位数当基线。
3. **data/validate/record_results 的重尾被笼统归为"偶发灾难性慢调用"**：这些是确定性/计算节点，p90 96s 与 max 765-783s 更可能来自内部重试（validate 的 Gate 检查里若调了 LLM 或重 I/O，则另说）。建议 P0-4 在三个节点内部加一条秒级分段日志（哪个子步骤慢），再决定是加预算还是修内因。
4. **quality 红线段落 (§5) 无新增动作**：修正版没回答"若 P0-3 熔断真的触发，哪些质量字段会降级、由谁判定、是否计入 best-so-far"。建议给熔断事件本身打 `degraded` 标记并纳入报告血统（lineage），否则"加速不降质"无法审计。

---

## 六、执行顺序修正建议（在原修正版之上叠一层）

```
P0-1a  给 research_planner 的单次 LLM 调用加 30s 独立超时（替代只靠共享预算）
P0-2a  补 [SELF-HEAL][PROFILE] 耗时与失败组计数；validate/data/record_results 加节点内分段日志
P0-4   同版本、同类型、干净环境跑真实报告；对比 P0-1a/P0-2a 后的 [PROFILE]
P0-3   基于 P0-4 分段数据做全局墙钟预算 + 熔断（先 data→validate→record_results 三个确定性节点）
P1     按维度动态注入（等 KB/MKB 引用门禁稳定）+ Gate 反馈维度化
```

核心改动：**在"全局预算"之前，先砍单次超时（180s→30/60/90s 分级）与补自愈/验证的段级观测**。这两个是确定性、低风险、不改语义的先手；全局预算留给 P0-4 证明仍存在的剩余尾部。

---

## 七、一句话结论

> 修正版已经把方向纠对：真瓶颈是"两个 LLM 大节点 + 重尾极值"，charts/asyncio/全局缓存可以明确不做。代码核验支持其绝大多数判断。真正的下一步不在修正版里，而在两处更细的刀口：**① 把"预算熔断"升级为"调用级超时 + 僵尸线程治理"，② 在写全局预算前先补 merge/自愈/验证节点的段级观测**。做到这两点，P0-4 才不是又一次猜，而是真数据的第二次迭代。

---

## 附：本次审计未验证项（诚实边界）

- 未跑真实报告（无网络 e2e / 沙箱空转无法验证 LLM 长尾），P0-4 的"155s→45s"与 write_sections 的组级分布属于**代码推演 + 历史日志**，不是本轮实测。
- 未检查 `docs/FIX_REPORT_research_planner_budget_20260907.md` 的 6 个测试在本次运行环境是否仍绿（前序全量推进报告 127 项通过，本轮未重跑）。
- PROFILE 的 424 行原始日志文件路径未在本文档内逐一枚举（历史运行日志散落在仓库 logs/ 与 docs/ 之外），引用时以 `PROFILE_BOTTLENECK_ANALYSIS_20260907.md` 的聚合口径为准。
