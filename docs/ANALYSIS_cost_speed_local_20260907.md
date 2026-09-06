# 2号分析师：成本、耗时、本地模型与顶级解法分析

> 日期：2026-09-07
> 范围：基于实际代码审计 + 官网价格/公开资料的工程分析，不含代码改动
> 适用对象：二号分析师（SAC 结构分析框架 + E2EOrchestratorV2 + IronGate）

---

## 1. 背景与问题清单

本轮要回答四件事，它们其实指向同一个工程问题：**如何在不牺牲报告质量红线的
前提下，把 token 成本和端到端耗时压下去**。

1. 信息调研交给 Kimi，token 费用是否偏贵？有没有更有性价比的方案？
2. 管线写报告时间很长，维度写已经并行，为什么还是慢？
3. 这两个问题，网上（社区/论文/顶级项目）有哪些解法？
4. 本地有 Qwen3-30B-A3B，能否充分用起来？有没有更好的推荐方案？

---

## 2. 结论速览

- **Kimi 偏贵，但不是最贵**。同任务下 DeepSeek V3.2-Exp（缓存命中）约便宜一个
  数量级；正确姿势是“DeepSeek 缓存层当主力 + 本地批量层打杂 + Kimi 只打硬仗”。
- **慢的根因不是并行不够，而是 attempt 轮次的串行尾巴**：`attempt>0` 时每轮
  DeepSeek 审稿 + 整篇 2 万字重写（`max_tokens=16000`），且图表/compute/enrich/
  cross_validate 每轮重跑，只有首轮数据采集走缓存。
- **本地 Qwen3 能接，代码已留口子，但当前只是 priority=9 的最后兜底**，健康云
  链路上不会被选中。要“充分用起来”，得靠节点级 pin 和角色分工，不能整篇切本地。
- **更好的方案是三层混合路由**：本地（批量短任务/草稿）+ DeepSeek V3.2 缓存
  （write/merge/revise 质量红线）+ Kimi K2（agentic 硬调研），并用
  Dagster/STORM/vLLM prefix cache 那套思路做增量与并行。

---

## 3. 代码事实与证据（先看清现状）

### 3.1 Provider 路由现状

- [core/deepseek_client.py](../../core/deepseek_client.py:169) 定义 provider 优先级：
  `opencode_go(1) → deepseek(2) → zhipu(3) → openrouter(4) → zen(5) →
  ollama_local(9) → agent_provider(10)`。数字越小越优先。
- [core/deepseek_client.py](../../core/deepseek_client.py:279) 启动时自动探测
  `OLLAMA_BASE_URL`（默认 `http://localhost:11434/v1`），探测到就注册
  `ollama_local`，模型列表来自 `/api/tags`。
- **关键结论**：本地模型注册为“云端全挂时的最后兜底”，云端健康时几乎永远轮不到
  它。这就是“接了但没充分用起来”的直接原因。
- [pipeline/route_policy.py](../../pipeline/route_policy.py:25) 支持双模式节点级混编
  路由：
  - `perf` 性能模式：write/merge/revise/gate_review 全走 deepseek（质量红线）；
    extract 走 openrouter；roundtable 走 opencode_zen。
  - `train` 训练模式：write/revise 走 agent_provider（Marvis 免费草稿）；
    merge 走 openrouter；gate_review 仍走 deepseek（终审保底）。
  - 每个节点可用环境变量覆盖，如 `NODE_PROVIDER_MERGE=deepseek`、`NODE_PROVIDER_EXTRACT=ollama_local`
    （见 [route_policy.py](../../pipeline/route_policy.py:88) `resolve_provider`）。
- [pipeline/e2e_orchestrator.py](../../pipeline/e2e_orchestrator.py:699) 草稿 provider
  优先级：`LLM_PROVIDER` > `DRAFT_PROVIDER` > 按 `RUN_MODE` 路由。

### 3.2 耗时瓶颈的事实

- [core/settings.py](../../core/settings.py:44)：`MAX_ATTEMPTS` 默认 3。
- [pipeline/e2e_orchestrator.py](../../pipeline/e2e_orchestrator.py:225)：数据节点
  首轮采集 + 重试轮缓存；但**图表、compute、enrich、cross_validate 每轮重跑**。
- [pipeline/e2e_orchestrator.py](../../pipeline/e2e_orchestrator.py:810)：`attempt>0`
  时每轮额外跑 DeepSeek 审稿（gate_review）+ 整篇重写（免费模型 reroute 到 write
  provider，`max_tokens=16000`），且同轮不重新过 Gate。
- [pipeline/section_writer.py](../../pipeline/section_writer.py:2710)：维度级并行写 +
  2 秒错峰 + 自愈重试已经存在，说明**写段本身不是主要瓶颈**。
- 观测设施已就位：[pipeline/e2e_orchestrator.py](../../pipeline/e2e_orchestrator.py:2215)
  附近有 `[PROFILE]` 节点级耗时日志；`best_so_far` / 语义 early-stop / stall 检测
  已存在。

---

## 4. 费用对标（问题 1）

以下为官网/公开定价（2026-09 时点），**实际以你的账单和官网最新价为准**：

| 方案 | 输入 | 输出 | 缓存命中 | 定位 |
|---|---|---|---|---|
| Kimi K2 | $0.60/M | $2.50/M | $0.15/M | agentic 硬调研、强推理 |
| DeepSeek V3.2-Exp | ~¥2/M（未命中） | ~¥3/M | ~¥0.2/M | 主力写作/大输入可缓存任务 |
| OpenAI Batch API | 全量约 5 折 | 同左 | 可与 prompt caching 叠加 | 离线/大批量 |
| 本地 Qwen3-30B-A3B | ~电费 | ~电费 | 天然缓存 | 批量短任务、草稿、校验冗余 |

**结论**：

- 调研类任务“读多写少、提示词可复用”，稳定前缀缓存命中后 DeepSeek 明显更划算。
- Kimi K2 的差异化价值在 agentic 多步检索和工具调用，适合“只打硬仗”，不适合整条
  管线铺开。
- 本地模型不是用来“省钱替代 DeepSeek”，而是把零边际成本的量（抽取、分类、标题、
  冗余评审、训练草稿）从云端搬走。

---

## 5. 写报告慢：根因与解法（问题 2）

### 5.1 为什么并行到顶还是慢

时间没有花在“写得慢”，而是花在每一轮 attempt 的**串行收尾链**：

```
并行写 N 段（已完成）
  → 串行 merge（整篇组装）
  → Gate 整篇判定
  → 失败则 attempt+1：
       DeepSeek 审稿（gate_review，串行）
       → 整篇 2 万字重写（max_tokens=16000）
       → 图表/compute/enrich/cross_validate 全部重跑
  → MAX_ATTEMPTS=3 → 最坏 ×3
```

再加上单次 HTTP 超时 180-300s，失败与重试会进一步放大墙钟时间。

### 5.2 可落地的改法（按性价比排序）

1. **attempt 轮只重写失败维度/段落，再 diff merge**，而不是整篇重写。代码里
   `rewrite_indices` 已留了局部修订的入口（`e2e_orchestrator.py` write_sections），
   把“整篇重写”收敛成“失败段重写”。
2. **图表与计算按 data hash 增量缓存**：数据没变就不重跑 chart/compute/enrich/
   cross_validate，跳过“每轮全量重算”。
3. **Gate 半程评分**：写作中途按维度给分，失败维度提前暴露并提前重写，而不是等
   整篇写完才 Gate、失败后又整篇返工。
4. `MAX_ATTEMPTS` 降到 2；打开 `LLM_RESPONSE_CACHE=1`，并把稳定 system 前缀纳入
   缓存键设计，吃 API 侧 prompt caching。
5. **先用 [PROFILE] 日志跑一版真实报告**，看 top 耗时节点，再对最贵的一格动刀，
   避免凭直觉优化。

---

## 6. 本地 Qwen3-30B-A3B：能用，但要用对地方（问题 4）

### 6.1 硬件与模型事实

- MoE 架构：总参数约 30B，每 token 仅激活约 3.3B，单卡吞吐优秀。
- 24GB 显存 Q4_K_M 可跑（权重约 19GB）；实测 RTX 4090 解码约 120-196 tok/s，
  RTX 3090 约 90 tok/s（社区实测，依量化/上下文浮动）。
- 默认上下文 32K，官方支持 YaRN 扩到约 131K；2 万字级报告 + 提示词很容易顶满，
  长上下文会显著吃掉 KV 显存。
- **质量边界**：3B active 撑不起 2 万字跨章一致性、So What 链与 Bold Call 级
  长程论证，不能承担 write/merge/revise 的质量红线。

### 6.2 代码怎么接（零改动到小改动）

当前自动注册只认 Ollama 的 `/api/tags`。最省事路径：

| 目标 | 设置 |
|---|---|
| 轻量提取/摘要/分类走本地 | `NODE_PROVIDER_EXTRACT=ollama_local` |
| 训练模式草稿/修订走本地 | `RUN_MODE=train` + `NODE_PROVIDER_WRITE=ollama_local` |
| 冗余评审席走本地 | `CRITIC_LOCAL=1`（[core/tools/critic_panel.py](../../core/tools/critic_panel.py:165)） |
| 无 agent 时的对侧校验 | 置 `HAS_AGENT=0`（自动落到 `ollama_local`，[llm_checks_mixin.py](../../pipeline/checks/llm_checks_mixin.py:158)） |
| perf 模式质量红线 | 不覆盖，保持 deepseek |

两个注意点：

1. provider 被 pin 后，若传入的 model 不在本地模型列表，代码会自动改用 Ollama
   返回的第一个模型（[core/deepseek_client.py](../../core/deepseek_client.py:666)）。
   想精确跑 Qwen3，让 `/api/tags` 中它排第一，或后续给它加一个 `LOCAL_MODEL` pin。
2. 若用 vLLM 的 OpenAI 兼容端点换掉 Ollama，`/api/tags` 探测会失败导致不注册；
   简单场景直接跑 Ollama，要吞吐（连续批处理 + prefix cache）再考虑 vLLM，并小改
   注册段支持 `LOCAL_BASE_URL`。

### 6.3 推荐的混合分工

| 节点 | 现状 | 建议 provider | 理由 |
|---|---|---|---|
| extract/summarize/分类/图表标题 | openrouter / agent | 本地 | 短输出、可校验、量大 |
| train 模式草稿与修订 | Marvis | 本地 | DeepSeek 终审 merge/gate_review 保底 |
| perf 模式 write/merge/revise/骨架 | deepseek | 保持 deepseek | 质量红线 |
| LLM 数据校验、圆桌冗余席 | agent/deepseek | 本地做异源对侧 | 双模型对抗、防同源偏差 |
| agentic 硬调研 | Kimi K2 | 保持 Kimi | 长程检索与工具调用 |

**反面提醒**：如果本地草稿导致 Gate 失败率明显高于 Marvis，会触发更多轮整篇重写，
反而更贵更慢。先小样本验证，再放量。

---

## 7. 网上顶级解法对照（问题 3）

| 思路 | 代表方案 | 映射到 2 号 |
|---|---|---|
| 节点级增量重跑 | Dagster / Flyte / Temporal | 失败只重跑失败节点；图表/计算按 data hash 缓存 |
| 并行分块写 + 单次合并 | STORM（论文/实现） | 已有维度并行写；把“整篇重写”改成“段级 diff merge” |
| prompt caching 分层 | Anthropic/OpenAI 缓存、微软缓存研究 | 稳定 system 前缀纳入缓存键；`LLM_RESPONSE_CACHE=1` |
| 推理层提速 | vLLM prefix cache / continuous batching / speculative decoding | 本地 Qwen3 承担批量短任务与并行初稿 |
| 弱稿并行 + 强模型择优 | best-of-N、cascade | 复用已有 `best_so_far`/early-stop，扩展“半程 Gate 评分” |
| 离线批量折扣 | OpenAI Batch API（约 5 折） | 大批量短任务走 batch，可叠加缓存 |

**一句话总结**：2 号的架构骨架（双模式路由、质量门禁、并行写、自愈重试、观测日志）
已经超过多数自研管线；缺的不是“更强的并行”，而是“更聪明的重跑范围”和“分层算力
分工”。

---

## 8. 下一步最小落地清单

1. 跑一版真实报告，读 `[PROFILE]` 日志，确认 top 耗时节点（写、merge、Gate 轮数）。
2. attempt 轮收敛为“失败段重写 + diff merge”，图表/计算按 data hash 增量缓存。
3. `MAX_ATTEMPTS=2`；开 `LLM_RESPONSE_CACHE=1` 并整理稳定 prompt 前缀。
4. 本地层先只 pin `NODE_PROVIDER_EXTRACT` 与训练模式草稿，小样本对比 Gate 失败率。
5. 若显存 <24GB，不建议上 Qwen3-30B-A3B 跑长报告；同量级备选可关注 2026 年发布
   的 GLM-4.7-Flash（第三方评测称同卡量级更强，需自行验证后决定是否换）。
