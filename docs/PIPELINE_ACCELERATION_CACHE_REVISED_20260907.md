# 管线加速 · 超越升级版修正（Prompt Cache 真实经济 + 并行 fan-out 修正）

**日期**：2026-09-07
**修正对象**：`docs/PIPELINE_ACCELERATION_BEYOND_UPGRADED_20260907.md`（下称"超越版"）
**修正依据**：DeepSeek 官方缓存规则核实 + 本仓代码锚点核对
**一句话**：超越版把 Prompt Caching 单列最高 ROI 是**对的**，且 DeepSeek 真实经济（无 write 费、30-120x 折扣）让它比超越版算的更值；但超越版有三处事实错误——其中"8 组并发 7 组命中"的乐观假设，直接高估了首轮收益。**真正红利在 attempt 复用 + cascade 收敛 + 同报告粘性路由**。

---

## 一、超越版三处事实修正

### 修正 1：DeepSeek 是"前缀严格匹配"，不是"partial match 有折扣"

| 超越版声称 | DeepSeek 官方规则（核实） | 后果 |
|---|---|---|
| "64-token 粒度（partial match 也有折扣）" | **前缀从 token 0 完全一致才命中**；64 token 只是存储单位；中段部分匹配**永不命中** | 修正版更严：稳定前缀 + 动态后缀不是优化选项，是**命中唯一前提** |

**工程推论**：任何易变内容（timestamp/日期/请求 id/无序 tool 列表）放进前缀区 = 整条链缓存报废。这是缓存设计的第一铁律。

### 修正 2：DeepSeek 经济被低估——无 cache write 费，折扣 30-120x 而非 90% off

| 维度 | 超越版假设（沿用 Anthropic 模型） | DeepSeek 实际（2026-08 调价后） |
|---|---|---|
| cache write | 1.25x（Anthropic 收费） | **无 write 费**（自动磁盘缓存，免费） |
| cache read | 0.1x（90% off） | **~0.03x（约 97% off）**：V4 Pro $0.022 vs miss $0.66 |
| TTL | 5min | **无 TTL**（best-effort，闲置自动清） |

**修正后的 8 组经济**：`1.0 + 7×~0.03 ≈ 1.2x` vs 不缓存 `8x`——比超越版的 1.95x 更优（前提：命中成立，见修正 3）。

### 修正 3（最关键）：并行 fan-out 首轮几乎不命中，"8 组 7 命中"是乐观假设

**DeepSeek branching 规则**：发 `A+B` 再发 `A+C` → 第二次**完整 miss**（系统要到第三次 `A+D` 才把共享 `A` 存为单位）。我们的 8 个维度组正是"共享前缀 + 各自分支"，且 ThreadPool **并发**发出 → 第一组写前缀时其余已上路，**首批 8 组几乎全 miss**。

**真正的缓存红利在**：
1. **attempt 循环**：attempt 0 写前缀 → attempt 1/2 复用（前缀不变，仅尾部 gate feedback 变）——DeepSeek 无 TTL，磁盘缓存跨 attempt 存活；
2. **跨报告**：同类型稳定 system prompt；
3. **串行/错峰**：组间 2s stagger 让后组可能吃到前组刚写的前缀（部分命中）。

**因此修正收益模型**：首轮并行命中≈0；命中主要来自 attempt 复用 + cascade 收敛后的少数集中调用。cascade 与缓存是**乘数关系**——调用越少越集中，前缀越稳定，命中越高。

---

## 二、本仓代码核实（修正版的事实基础）

| 锚点 | 现状 | 含义 |
|---|---|---|
| `core/deepseek_client.py` call_llm | **不读 `prompt_cache_hit_tokens` / `cached_tokens`** | 缓存命中率盲飞——无法知道重排是否生效 |
| `core/smart_router.py` | 多 provider 各有 base_url；perf 质量红线 pin deepseek | 同报告多数调用钉 deepseek（粘性基础好），但 fallback 链跨 provider 时**缓存隔离** |
| `section_writer.py` 组 prompt 前缀 | 含 `《{asset}》` + `本次分析唯一标的：{asset}` | 同报告 8 组前缀稳定（asset 相同）→ 可命中；跨报告 asset 变 → 不命中（可接受） |
| `deepseek_client.py:324` | 有应用侧响应缓存（`LLM_RESPONSE_CACHE`），默认关 | 与写改循环采样语义冲突，须谨慎（见 §三.4） |

---

## 三、修正后的执行路线（超越版修正）

### 第 0 刀（新增，P0）：缓存可观测性——先装仪表再开车
- `core/deepseek_client.py` 每次调用读 usage 的 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`，记 `[CACHE] provider=X hit_rate=Y% hit=H miss=M`；命中率 <30% 告警。
- **验收**：跑一份真实报告，日志能看到每调用命中率（当前是 0 观测）。
- 为什么第一：没有它，后续所有 prompt 重排/粘性路由做没做对都是盲飞。

### 第一刀：stable-first prompt 重排（P0，0.5-1 天）
- 组 prompt 结构：`[system 稳定区]`（你是什么/任务）+ `[SAC 框架]` + `[方法论规则]` + `[合规]` + `[数据锚卡]` + `[维度指令]` + `[gate feedback 尾部]`。
- **铁律**：稳定区不得含 timestamp/日期/请求 id/asset 依赖的动态内容；asset 锚定若必须在，放稳定区且同报告内不变（已满足）；gate feedback 只追加在尾部，不插入前缀。
- **验收**：attempt 1 相对 attempt 0 的 `prompt_cache_hit_tokens > 70%`。

### 第二刀：同报告粘性路由（P0，防缓存最大敌人）
- DeepSeek 缓存按上游隔离；跨 provider/跨 OpenRouter 上游弹跳 = 永不相交的 KV 缓存。
- 动作：perf 模式质量红线节点已 pin deepseek（好）；补一条**同报告内不弹跳**保证——`call_llm` 对同一 trace/job 记录"首个成功 provider"，同批后续调用优先复用该 provider（除非熔断）。
- **验收**：同报告无 provider 弹跳日志。

### 第三刀：全局并发闸 + 分层超时（承接升级版，P0）
- `core/llm_concurrency.py` semaphore + call_llm 包一层 + connect/read 拆分（承接，不展开）。

### 第四刀：cascade + attempt 当缓存消费者（P0-P1，与缓存乘数联动）
- 骨架便宜模型 → 深化只改 Gate 标红维度 → attempt 1/2 因前缀稳定吃缓存命中。
- L2 应用侧缓存（`dimension_cache_key` 含 data_hash + gate_feedback_hash）——**安全前提**：feedback 变即 miss，不破坏写改循环采样；只对确定性/数据未变节点开，与 `deepseek_client.py:324` 警告对齐。

---

## 四、收益模型（修正后）

| 方案 | 修正后单独效果 | 说明 |
|---|---|---|
| 分层超时 + 并发闸 | 重尾 13min→90s，消 429 雪崩 | 承接升级版 |
| **缓存可观测 + stable-first** | 命中率可测；attempt 1+ 命中 >70% | 第 0+一刀的验收 |
| **粘性路由** | 消除"跨上游永不命中" | 缓存成立的前提 |
| cascade | 调用 20-50→15 | 与缓存乘数 |
| **叠加** | 首轮不指望命中；**attempt 轮与后续报告**吃 ~90% input 折扣 | 修正超越版"8 组 7 命中"为"跨轮/跨报告命中" |

**修正后的现实预期**：单份报告**首轮**主要靠 cascade（调用次数↓）+ 超时/并发闸（重尾↓）；**缓存红利体现在**同报告 attempt 1/2 + 连续跑同类型多份报告时。单份首轮降幅以 40-55% 计（超时+并发+cascade），多份/多轮场景才到 63-74%。

---

## 五、验证标准（每条可测）

- [ ] `[CACHE]` 日志出现，命中率可回看（第 0 刀验收）
- [ ] attempt 1 的 `prompt_cache_hit_tokens` > 70%（stable-first 生效）
- [ ] 同报告无跨 provider 弹跳（粘性路由生效）
- [ ] Gate score 不降（每条质量红线保留：SAC≥70% / 来源≥30% / IronGate 全过）
- [ ] 连续跑 3 份同类型报告，第 2/3 份 input 成本显著下降（跨报告缓存红利）

---

## 六、一句话结论

> 超越版把 Prompt Caching 单列最高 ROI 是对的，且 DeepSeek 真实经济（无 write 费、30-120x 折扣）比它算的更值；但它"partial match 有折扣"和"8 组 7 命中"两处是错的——DeepSeek 是前缀严格匹配，并行 fan-out 首轮几乎不命中。修正后：**先装缓存仪表（第 0 刀）→ stable-first 重排 → 同报告粘性路由 → 让 attempt 循环和 cascade 吃缓存**。真正的缓存红利不在"8 组并发"，而在"同一前缀被第二次、第三次调用复用"。
