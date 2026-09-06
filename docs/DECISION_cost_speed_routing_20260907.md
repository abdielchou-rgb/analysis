# 成本 / 速度 / 本地模型路由 · 决策记录

**日期**：2026-09-07
**性质**：综合 `docs/ANALYSIS_cost_speed_local_20260907.md` + 三轮 web 顶级解法调研（自优化停止 / 模型级联 / 成本路由）+ 本仓代码事实核验的**决策记录**。非代码改动。
**一句话**：省成本/省时间的杠杆不是"换更便宜的模型"或"更强的并行"，而是 **按测得增益停重写、按任务类别路由模型、把批量短任务压到本地+免费层**。

---

## 一、代码事实核验（相对原报告的修正）

| 原报告声称 | 磁盘实测 | 判定 |
|---|---|---|
| provider 优先级 opencode_go(1)→deepseek(2)→…ollama(9) | `core/deepseek_client.py:170` 属实；但 `route_policy.py:25` 注释称"opencode_go 已损坏，写作任务切 zhipu"，`smart_router.py:126` 又称"优先 opencode_go" | ⚠️ **三处对 opencode_go 现状表述冲突**（SSOT 同类问题） |
| ollama 自动探测 `/api/tags` | L280-291 属实 | ✅ |
| MAX_ATTEMPTS=3 | `settings.py:46` 属实 | ✅ |
| "整篇 2 万字重写" 是慢的根因 | **局部修订已存在**（`rewrite_indices` + `_locate_failed_segments`，R13 Phase4，e2e L728-733） | ⚠️ 部分过时 |
| attempt 轮串行尾：审稿→重写→图表/compute 重跑 | 审稿 L809 attempt>0；数据采集有缓存，**计算无 data-hash 缓存** | ✅ 成立 |

**核验结论**：原报告方向正确；真正的杠杆缺口是 **① 计算层无 data-hash 缓存 ② attempt 收敛策略未用"增益停止" ③ 本地层是静态兜底而非 cascade**。

---

## 二、三个决策问题：顶级实践给的答案

### Q1 「质量 ≥0.8 就不重写」——0.8 是好的停止线吗？

**结论：0.8 只配当启发式富余线，不配当主停止条件。顶级做法是"过线 + 增益停止"。**

| 做法 | 出处 | 要点 |
|---|---|---|
| **按一步增益停** | Optimal Stopping / GainNet (arXiv 2604.02035) | 只当"预期下一步提升 > 本次成本"才继续；用小回归器预测增益（评审 embedding、编辑距离、轮次）。固定 8 轮上限的 60-70% 算力拿到 96-99% 质量。**模型自述"改不动"不可靠** |
| **语义早停** | Semantic Early-Stopping (arXiv 2606.27009) | 编辑幅度近似指数衰减，前 1-2 轮吃掉多数改进；监控相邻稿语义距离，停在平台期。**纯质量门策略可能适得其反**，需与收敛信号结合 |
| **合取停止** | 工程共识 | verifier 过 OR（自评 OK 且 ≥2 轮）OR 达上限；上限 ≤4，超 3-4 轮不收敛 = generator prompt 坏了 |

**对本仓的含义**：若 0.8 指 Gate error-mean（PASS=0.78），0.8 只高 0.02 = 刚过线就停，偏低。改造：**Gate 过线（独立 verifier）为主闸 + 两轮提升 <ε 停**，质量分仅作"富余线"。

### Q2 没有 OpenAI API，Batch 换什么？

**结论：Batch 只是"便宜"的一种，本仓已有更便宜的现成杠杆——直接砍掉 Batch 想法。**

| 替代杠杆 | 本仓现成度 | 覆盖任务 |
|---|---|---|
| **本地批量（零边际成本）** | `ollama_local` 已注册；Qwen3-30B-A3B Q4 19GB/4090 约 120-196 tok/s | extract/分类/标题/冗余评审（小模型几乎总能胜任的固定分类、结构化抽取、格式化） |
| **免费 provider 队列** | opencode_go(1,免费)/opencode_zen(5)/agent_provider(10,免费) | 非实时大批量排队，比 batch 折扣省更多（省 100%） |
| **DeepSeek 缓存命中档**（¥0.2/M in） | 稳定 system 前缀吃 prompt caching | 云端"准 batch 价" |

实测佐证：工程案例成本降 88% = 44% 本地 7B + 41% 缓存命中 + 仅 8% 到 frontier（Local-Splitter, arXiv 2604.12301）。真正"便宜+离线+上云大批量"才考虑 OpenRouter batch 或 DeepSeek 官方——本仓结构下非必需。

### Q3 Kimi 必要吗？

**结论：不必要作为默认；只保留给"真·长程开放探索"节点。多数调研是 DeepSeek 舒适区。**

| | Kimi K2-Thinking | DeepSeek V3.2 |
|---|---|---|
| 定位 | "autonomous researcher" 耐耗型 | "strategic planner" 精准型 |
| 工具调用 | 200-300 步连续探索、全程保留推理史 | 先验参数再调用、可丢推理史省 context |
| 适合 | 开放探索：网页浏览、找未知 | 明确定义：拉数据、查询、1-2 步 |
| 价格(OpenRouter) | $0.60 in / $2.50 out | $0.27 in / $0.41 out（约 6x 差） |
| 切换 | slug 切换即可 | — |

**替代排序**：① DeepSeek V3.2/V4 当调研主力（便宜数量级）；② 本地 Qwen3-30B-A3B agent 变体（短链调研，零边际成本）；③ 免费层覆盖简单检索；④ 真需耐力探索才按需切 Kimi。

**顶级提醒**：模型换代快（Kimi K3 / DeepSeek V4 已现），"昨天最优路由今天未必最优"——把调研任务分"开放探索 vs 有限提取"两类，小样本测 Gate 失败率再定，不长期绑定单模型。

---

## 三、落地决策（本记录定案）

1. **重写停止策略**（P0）：Gate 过线为主闸 + 两轮提升 <ε（建议 ε=0.02-0.05）停；`MAX_ATTEMPTS` 上限 3 保留作 failsafe。质量 0.8 降级为"富余线"，不作为主条件。
2. **计算层 data-hash 缓存**（P0）：chart/compute/enrich/cross_validate 按 data hash 增量——数据没变不重跑（这是真 P0，原报告改法 2）。
3. **开 `LLM_RESPONSE_CACHE=1`** + 稳定 system 前缀入缓存键（最便宜的杠杆）。
4. **批量短任务路由**：extract/分类/标题/冗余评审 → `ollama_local`（本地）/免费层；perf 模式 write/merge/revise/gate_review 保持 deepseek 质量红线。**不做 Batch API**。
5. **调研节点分级**：识别"开放探索"节点（保留 Kimi 候选）vs "有限提取"节点（DeepSeek/本地）；上线前小样本 A/B 测 Gate 失败率。
6. **provider 现状冲突修复**（SSOT）：统一 opencode_go 在 deepseek_client / route_policy / smart_router 三处的"可用/损坏"表述——单一事实源。
7. **先 profile 再动刀**：跑一版真实报告读 `[PROFILE]` 日志，确认 top 耗时节点后按上述优先级逐项改。

---

## 四、来源

- Optimal Stopping for Iterative Self-Refinement: https://clawrxiv.io/abs/2604.02035
- Semantic Early-Stopping for LLM Agent Loops: https://arxiv.org/html/2606.27009v1
- StillMe RewriteLLM cost-benefit policy: https://github.com/anhmtk/StillMe-Learning-AI-System-RAG-Foundation/blob/main/docs/COST_BENEFIT_REWRITE.md
- Local-Splitter (7 tactics): https://scirate.com/arxiv/2604.12301
- LangChain Switchyard (frontier-needed fraction): https://www.langchain.com/blog/switchyard-agent-routing-benchmark
- LLM Routing Strategies 2026: https://jobsbyculture.com/blog/llm-routing-strategies-2026
- DeepSeek V3.2 vs Kimi K2 (CanopyWave): https://canopywave.com/blog/deepseek-v32-vs-kimi-k2-thinking
- OpenRouter 实时比价: https://openrouter.ai/compare/deepseek/deepseek-v3.2-exp/moonshotai/kimi-k2-0905
