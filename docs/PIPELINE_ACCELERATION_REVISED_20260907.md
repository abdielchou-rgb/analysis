# 管线加速 · 修正版路线（基于真实 PROFILE 数据）

**日期**：2026-09-07
**修正对象**：`docs/PIPELINE_ACCELERATION_ANALYSIS_20260907.md`（下称"原方案"）
**修正依据**：424 行真实 `[PROFILE]` 日志聚合（docs/PROFILE_BOTTLENECK_ANALYSIS_20260907.md）+ 代码现状核对
**一句话**：原方案是"教科书式加速清单"——方向对但**脱离本仓库真实瓶颈**：漏掉实测 155s 的 research_planner、把 1.5s 的 charts 当优化目标、把已实现的段级重写当待办、推荐会破坏修订语义的缓存。本修正版用真实数据重排优先级，**承认已做对的、剔掉伪优化、补真缺口**。

---

## 一、原方案逐条修正（对代码事实）

| 原方案项 | 声称 | 代码/实测事实 | 修正判定 |
|---|---|---|---|
| §0.2 瓶颈表 | charts 10-20s / 4-7% | 实测 charts 中位 **1.5s**（max 1.9s） | ❌ 伪优化目标 |
| §0.2 瓶颈表 | 漏列 research_planner | 实测中位 **155s**、p90 **1219s**（DAG 图有它、瓶颈表无它） | ❌ 最大遗漏 |
| ⑤⑥⑦ | attempt 是"整篇 2 万字重写" | 代码已有 `_locate_failed_segments`+`rewrite_indices` 段级重写（e2e L766-770） | ❌ 已实现一半 |
| ①③④ | "风险零" | asyncio 改 23 节点图、provider 预探测、DAG 改依赖均非零风险 | ❌ 低估风险 |
| ⑤ 缓存 | gate_feedback 变化≤20% 复用 | 写作修订循环依赖轮间采样差异；全局缓存破坏 repair/STALL（deepseek_client 源码注释明确） | ❌ 危险建议 |
| ② 按维度动态注入 | 8-12K→2-4K token | 方向正确，是唯一实质杠杆 | ✅ 保留（P1） |
| ⑥⑦ 骨架/精准 Gate | 让失败段局部重写 | rewrite_indices 已在；缺"Gate 反馈维度化" | ✅ 部分保留 |
| ⑧⑨ compute/charts 预热 | 省 15-30s | charts 1.5s 无意义；compute 提前需 data 依赖分析 | ⚠️ 低价值 |

---

## 二、真实瓶颈排行（424 行 PROFILE 实测，中位数）

| 节点 | 中位 | p90 | max | 性质 |
|---|---|---|---|---|
| **research_planner** | **155s** | 1219s | 1219s | LLM 问题生成（无预算时） |
| **write_sections** | **107s** | 412s | 2502s | 维度并行写 + merge |
| data_feeds | 35s | 104s | 113s | RSS/PDF/patent feeds |
| data | 15s | 48s | 783s | 主采集，**重尾** |
| critic | 15s | 48s | 272s | 双模型对抗 |
| record_results | 6s | 48s | 765s | **重尾** |
| validate | 4s | 96s | 370s | Gate，**p90 高** |
| charts | **1.5s** | 1.9s | 1.9s | 可忽略 |

**关键洞察**：真正耗时的两类——① 两个 LLM 大节点（research_planner + write_sections，中位合计 ~262s）；② **重尾极值**（data/record_results/validate 偶发 5-13 分钟，把单轮从 6 分钟拖到 40 分钟）。**不是 charts，不是"并行不够"。**

---

## 三、修正版优先级（按真实收益，替代原方案 §1/§5）

### P0-1 ✅ 已完成：research_planner 45s 共享预算熔断
- `question_tree_v2` 加 `llm_budget_s`（默认 45s）：超预算维度回落 v1 模板，`pool.shutdown(wait=False)` 让慢线程后台结束不阻塞主流程。
- 收益：中位 155s → 上限 ~45s，消除 20 分钟级最坏情形。
- 证据：docs/FIX_REPORT_research_planner_budget_20260907.md，6 测试绿。

### P0-2 ✅ 已完成：write_sections 段级 profile（组级 + merge 级）
- `_write_dimension_parallel` 每组写完后上报 `[DIM-PARALLEL][PROFILE]`，汇总最慢组并 ≥30s 告警；`_editor_merge` 加 merge 耗时日志。
- 收益：定位"哪个组/merge 拖到 107s/2502s"的前提（下一刀降档的数据基础）。
- 证据：docs/FIX_REPORT_section_profile_20260907.md，测试绿。

### P0-3 🆕 待做：全局耗时预算 + 重尾熔断（真缺口，替代原方案 ⑧⑨）
- **目标**：治 data（max 783s）/ record_results（765s）/ validate（p90 96s）的偶发灾难性慢调用。
- **做法**：e2e 单轮总预算（如 600s 墙钟），各节点共享；节点超预算→降级（缓存/本地兜底）而非无限等；`[PROFILE]` 已有观测，缺的是"预算执行器"。
- **收益**：消灭 5-13 分钟重尾——比 DAG 并行、asyncio 收益大得多。
- **风险**：需真实环境回归（不能沙箱空转验证）。

### P0-4 🆕 待做：真实报告跑一版，读三层 [PROFILE] 验证
- 用已就位的组级+merge 观测，跑一份真实报告，确认：(a) research_planner 是否 ≤45s；(b) 哪一组最慢（≥30s 告警）；(c) merge 是否慢。
- 这是"动下一刀前"的必经验证——没有它，任何降档/压缩都是猜。

### P1：按维度动态注入 prompt（原方案②，唯一实质杠杆，保留但延后）
- 方向对：8-12K→2-4K token 直接砍 LLM 处理时间。
- **前置**：KB/MKB 引用门禁（P1-2，codex 已接线 IronGate L428）先稳定——否则压缩会再次让方法论"进不了报告"（本轮 KB 落地的初衷）。
- 做法：`DIMENSION_INJECTIONS` 维度→注入子集映射 + 与 kb_citation_coverage 强检查联动。

### P1：Gate 反馈维度化（原方案⑦的一半）
- 已有段级重写（rewrite_indices）；缺的是把 Gate 反馈从"全文级"变"维度级"（哪些维度过/哪些挂、挂的原因），让 rewrite_indices 更精准。

### P2：明确不做 / 延后
- **charts 预热/缓存**（原方案⑨、① 中 charts 部分）：1.5s 无优化价值。
- **全局 asyncio 改造**（原方案③）：23 节点图改造高风险，收益被 research_planner/write 的 LLM I/O 主导、async 不改调用次数。
- **provider 每轮预探测**（原方案④）：已有熔断/路由，预探测增加开销。
- **response 缓存全局化**（原方案⑤）：破坏修订语义，明确否决。

---

## 四、组合效果（修正版）

| 组合 | 预估 | 说明 |
|---|---|---|
| P0-1 + P0-2（已完成） | 中位 262s→~155s（LLM 两大节点） | 已落地，等真实报告验证 |
| + P0-3 重尾熔断 | 消除 5-13 分钟极值 | 单轮从"最坏 40 分钟"变"最坏 ~10 分钟" |
| + P1 按维度注入 | LLM 处理再砍 ~40-50% | 需 KB 门禁稳定后做 |

---

## 五、质量红线（不变）

原方案 §4 的五条红线保留：SAC 覆盖率 ≥70%、来源标注 ≥30%、IronGate 全过、So-What 每段、目标价+评级+催化剂必含。每个加速改动上线前跑 before/after Gate score 对比。

---

## 六、执行顺序（替代原方案 §5）

```
已完成：P0-1（research_planner 预算）→ P0-2（段级 profile）
下一步（需真实环境）：
  Step 1  P0-4：跑一版真实报告，读 [PROFILE] 验证 P0-1/P0-2 生效 + 拿组级耗时分布
  Step 2  P0-3：按 Step 1 数据，给最慢节点加全局耗时预算 + 重尾熔断
  Step 3  P1：按维度动态注入（KB 门禁稳定后）+ Gate 反馈维度化
长期     P2 清单明确不做（charts 预热 / asyncio / provider 预探测 / 全局缓存）
```

---

## 七、一句话结论

> **原方案把加速当成"并行/异步/缓存"的工程题；真实数据证明它是"两个 LLM 大节点 + 重尾极值"的问题。修正版承认 P0-1/P0-2 已用真实数据做对，把下一步收敛为：跑真实报告验证 + 全局耗时预算治重尾（P0-3/P0-4），再谈按维度注入（P1）——charts/asyncio/全局缓存列为明确不做。**
