# 二号分析师 · 质量-速度总纲（顶级质量 + KB/方法论体现 + 快的统一框架）

**日期**：2026-09-07
**性质**：收编此前全部加速文档（PIPELINE_ACCELERATION_* 五份）的**顶层约束文档**——回答用户的核心命题："保证质量、保证知识库/方法论在每个文档充分体现、每篇顶级一流、又要写得足够快"。
**一句话**：质量是上限，速度是执行。**先立质量层为可测门禁，再让速度层只做零语义风险的优化，用"质量-速度五元组"验收每一刀**——任何让"快"吃掉"好"的改动都不允许上线。

---

## 〇、为什么前面的加速文档回答不了这个问题

| 文档 | 优化面 | 盲区 |
|---|---|---|
| ANALYSIS / REVISED / UPGRADED / BEYOND / CACHE_REVISED | 执行效率（省 token / 省延迟 / 缓存） | 假设"质量已达标，只差速度"——但质量是否达标恰恰是 20260907 KB 审计发现"未解决"的部分 |
| BEYOND_CACHE | 缓存三条持久化路径、staggered fan-out | 通篇没回答"让每篇顶级"要做什么；prompt 结构工程（按维度切 KB）可能直接伤害 KB 体现 |

**顶级解法的实证结论**（synthesis-trajectories, arXiv 2603.00686）：长文合成质量主要来自 **reasoning（规划/批判）而非 generation（草稿）**；高质量参考材料贡献 +36%。**质量杠杆在 plan/critique/grounding，不在缓存。**

---

## 一、质量层：把"顶级 + KB/方法论充分体现"变成四个可测门禁

"体现"不能是感觉，必须是门禁数字。质量层达标 = 以下**四绿缺一不可**：

| 门禁 | 现有状态 | 缺口 |
|---|---|---|
| ① SAC 维度覆盖 | ✅ IronGate `_check_sac_coverage`（必需维度全覆盖） | 无 |
| ② 来源标注 | ✅ `_check_evidence_layer` / `_check_inline_citations` / `_check_evidence_coverage` | 无 |
| ③ KB/方法论引用覆盖 | ✅ `kb_citation_coverage`（2026-09-07 codex 接线，IronGate L428 + e2e `set_kb_injection_counts`） | 目前 warning 起步；引用覆盖阈值待基线后上调 |
| ④ **方法论应用深度** | ⚠️ prompt 有"框架应用结论强制"（section_writer L1501/1530/2519），但**无门禁验证** | **真缺口**：检查每个注入的方法论框架，正文必须有"用该框架得出的具体结论"（非只提名字）——把"注入→引用→应用"闭环的最后一段补上 |

**质量层验收（每条文档）**：四绿才算"顶级"。
- 引用覆盖：注入 N 条 KB/MKB → 正文唯一引用 ≥ 阈值（当前 0.5 warning，基线后升 error）。
- **方法论应用（新增）**：注入的每个框架名，正文须出现"用【框架】分析得【具体结论】"式回指，否则该项红。

---

## 二、速度层：把加速刀分成"零语义风险"和"语义风险"两类

**铁律：改 prompt 内容的刀必须 A/B 过质量门禁；不碰 prompt 的刀直接做。**

### A. 零语义风险（直接做，不改变模型看到什么）
| 刀 | 出处 | 说明 |
|---|---|---|
| 分层超时（connect 5s + read 分档 30/60/90） | UPGRADED | 重尾 13min→90s |
| 全局并发闸（semaphore） | UPGRADED | 消除 429 雪崩 / 2502s 极值 |
| 同报告粘性路由 | CACHE_REVISED | 防跨 provider 缓存隔离 |
| 缓存可观测性（第 0 刀） | CACHE_REVISED | 读 `prompt_cache_hit_tokens`，命中率可回看 |
| 跨报告稳定前缀 | CACHE_REVISED | system+SAC+方法论+合规 完全一致（asset 移尾部） |
| 审稿模型保持强模型 | 本总纲 §三 | gate_review 已 pin deepseek（train 也如此）——不动 |

### B. 语义风险（必须 A/B：kb_citation + methodology_application + Gate score 不降才算过）
| 刀 | 风险 | 守门条件 |
|---|---|---|
| 按维度动态注入（8K→2K） | 切掉某维度该引用的 KB | 该维度保留其应引 KB 条目；引用门禁过 |
| stable-first prompt 重排 | asset/动态内容放错位 → 缓存报废或丢 KB | 前缀只放稳定内容；asset 移尾部 |
| **semantic cache / L2 响应缓存** | **复用 attempt 0 输出 = 跳过 critique→rewrite（质量主来源）** | **只缓存"已过 Gate 的维度"，不缓存任意输出；gate_feedback 变即 miss** |

---

## 三、cascade 的正确方向：规划/批判用强模型，草稿用便宜模型

论文证据（quality 来自 plan/critique，不来自 draft）直接给 cascade 定调——**当前 2hao 的分配与顶级证据相反，建议评估反转**：

| 角色 | 当前 | 顶级证据指向 | 建议 |
|---|---|---|---|
| 规划（research_planner/骨架） | deepseek + 45s 预算 | 规划决定结构质量 | 保持强模型 + 预算（已改） |
| 草稿（维度写作） | deepseek（perf 质量红线） | draft 不是质量主来源 | **可降档**：本地/免费草稿 → 强模型只审 |
| **批判/审稿（review/gate_review/critic）** | gate_review=deepseek（train 也如此，✅ 已保护）；critic=roundtable | **critique 是质量主来源** | **保持强模型，绝不能被缓存/semantic cache 绕过** |

**铁律**：质量层节点（审稿、Gate、方法论应用校验）永远强模型 + 永不过缓存；速度层节点（草稿、抽取、分类）才吃缓存/降档/并行。

---

## 四、联合验收：质量-速度五元组（每次改动必跑）

立一个固定评测集（5-10 份代表报告：industry_deep / listed_company / unlisted_company / earnings_notes / decision_memo），记录五元组：

```
gate_score           — 结构质量
kb_citation_cov      — KB/方法论引用覆盖
methodology_application  — 方法论应用深度（新增门禁）
report_cost          — input+output token 成本
report_wallclock     — 端到端耗时
```

**任何"加速"改动上线条件**：`report_wallclock ↓ 或不变` **且** 其余四项**不劣化**（质量平/升 + 快）。没有这个，无法回答"变快的同时是不是悄悄变平庸了"。

---

## 五、执行路线（质量先行 → 速度收编）

```
Phase 0（质量基线，先做）：
  1. 加 methodology_application 门禁（§一④）——把"框架应用结论强制"从 prompt 变成 Gate 检查
  2. 立五元组评测集 + 基线记录（5-10 份报告跑一次，存 baselines.json）

Phase 1（零语义风险加速，可并行）：
  分层超时 / 并发闸 / 粘性路由 / 缓存可观测 / 跨报告稳定前缀

Phase 2（语义风险加速，逐刀 A/B）：
  按维度动态注入 → 过五元组才留
  stable-first 重排 → 过五元组才留
  semantic cache → 只缓存已过 Gate 维度 → 过五元组才留

Phase 3（cascade 反转评估）：
  草稿降档（本地/免费）→ 审稿保持强模型 → A/B 对比五元组
```

---

## 六、文档关系

| 文档 | 关系 |
|---|---|
| PIPELINE_ACCELERATION_*（五份） | 收编为"速度层"执行细节；凡与质量层冲突者以本总纲为准 |
| MASTER_REVIEW_AND_KB_PLAN_20260907.md | KB 落地计划 → 质量层 ③④ 的来源 |
| kb_citation_mixin.py | 质量层 ③ 的实现（codex 已接线 IronGate） |

---

## 七、一句话结论

> **你要的"顶级 + 充分体现 + 快"不是三个并列目标，而是两个层：质量层是上限（四门禁：SAC 覆盖 / 来源 / KB 引用 / 方法论应用），速度层是执行（只做零语义风险优化 + 语义风险刀逐刀 A/B）。顶级质量来自规划与批判——批判不能被缓存绕过，草稿才可降档。任何加速改动用"质量-速度五元组"验收：快可以，但质量平/升是前提。没有这个约束，所有缓存/压缩刀都可能让"顶级"悄悄变成"更快但平庸"。**
