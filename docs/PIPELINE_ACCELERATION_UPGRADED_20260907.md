# 管线加速 · 升级版执行路线（补：分层超时 + 全局并发上限 + 缓存前缀 + 调用次数收敛）

**日期**：2026-09-07
**修正对象**：`docs/PIPELINE_ACCELERATION_HONEST_ASSESSMENT_20260907.md`（下称"诚实评估"）的执行路线
**新增依据**：LLM 生产级可靠性顶级实践（分层超时 / 熔断计数 / semaphore 并发上限 / 稳定前缀缓存 / cascade 调用收敛）+ 本仓代码锚点核对
**一句话**：诚实评估的三刀方向全对（超时分级 → 观测 → 按维度注入），但顶级解法会把它升级为"**四件套**"——每刀加一层机制，最终收敛的不仅是"每次更快"，还有"更少次调用"。

---

## 〇、诚实评估的路线 vs 本升级版

| 诚实评估的刀 | 保留 | 升级补强 |
|---|---|---|
| 第一刀 单次超时分级 180s→30/60/90 | ✅ | → **分层 + 自适应超时**（connect/read 拆分、按 p95 调） |
| 第二刀 merge/自愈段级观测 | ✅ | 保留（观测是后续所有刀的前提） |
| 僵尸线程善后 | ⚠️ 方向对 | → **全局并发上限（semaphore）**才是真解（线程不可杀，但可限制并发不叠加） |
| 第三刀 按维度动态注入 8K→2K | ✅ | → **稳定前缀 + 动态后缀**（顺带吃 provider 缓存命中） |
| 第四刀 Gate 反馈维度化 / Provider 路由 | ✅ | 保留；另加 **cascade 只深化失败维度**（收敛调用次数 20-50→15 内） |

---

## 一、第一刀升级：分层 + 自适应超时（替代"固定三档"）

**现状代码锚点**：`core/settings.py:115` `llm_http_timeout()` 默认 **180s 单值**；`core/deepseek_client.py:734/783` 用 `timeout=timeout or llm_http_timeout()`（openrouter 流式 `max(...,300)`）。

**顶级实践**（"Designing for Shared LLM Infrastructure"）：共享 LLM 端点延迟重尾（p99 ≈ 10×p50），按均值调参必然在负载下崩溃。要给每个请求**显式截止时间**，且**分层**：

1. **connect/read 拆分**：`requests`/`httpx` 支持 `(connect, read)` 元组。connect=5s（连不上立刻失败），read 才是主档位——比单值 180s 精确得多（当前 180s 是 read 超时，但 connect 挂死也等 180s）。
2. **节点级档位**（比全局 180 细）：
   | 调用 | 建议 read 超时 | 依据 |
   |---|---|---|
   | research_planner 单次 | 30s（已落地） | 短任务，模板可兜底 |
   | 组写作 `_call_llm` | 60-90s | 产出 1500-2500 字 |
   | merge `_llm_merge_once` | 45s | 单次大输入，重尾高发 |
3. **自适应（P1）**：按 `[PROFILE]` 观测的节点 p95 设 base，`base + 每 K token 加秒`，上限封顶——避免"固定 90s 对 2K token 太长、对 20K 又太短"。

**实现**：`call_llm(..., timeout=)` 已有透传（L918）；加 `settings.llm_read_timeout_s(node)` / `llm_connect_timeout_s()`，写作/merge 调用点显式传档位。

**验收**：`[PROFILE]` 中 validate/data/record_results 的 max 从 5-13 分钟降到 <90s。

---

## 二、僵尸线程治理升级：全局并发上限（semaphore）才是真解

**现状代码锚点**：`research_planner.py:195` 6 路线程、`section_writer.py:2860` 6-8 路组写作线程——各自 `ThreadPoolExecutor`，**互不感知**。僵尸线程（预算到点后 `shutdown(wait=False)` 留下的慢请求）会与后续组写作**同时压同一个 provider**，正是 429 连锁失败温床。

**顶级实践**：Python 线程不可杀（诚实评估判断正确），所以**别试图杀，限制"同时在飞"的总数**。方案：

1. **进程级全局并发闸**（最小改动）：一个模块级 `threading.Semaphore`（或 `core/llm_concurrency.py` 的计数器），所有 LLM 调用（research/写作/merge/自愈）进出都 acquire/release。上限按 provider 限流定：deepseek 类取 4-6，本地可高。
   ```python
   # core/llm_concurrency.py
   _SEM = threading.Semaphore(_CONCURRENCY)  # env LLM_MAX_CONCURRENT, 默认 6
   def llm_call_guard():
       return _SEM  # 调用方 with llm_call_guard(): requests.post(...)
   ```
2. **僵尸线程不再叠加**：僵尸占着一个 semaphore 名额 → 后续请求自然排队/降级，而不是"僵尸 + 8 组"无界叠加打挂 provider。
3. **熔断计数分类**（`deepseek_client.record_timeout` 已是半次，方向对）：补充——熔断 open 时 **fail-fast 到 fallback**，不再发起请求（`ai-fallback`/Claude breaker 模式：`allow_request()` 检查，open 直接 raise→fallback）。

**实现位置**：`core/deepseek_client.py` 的 `call_llm` 内（唯一 LLM 出口，所有调用必经）——包一层 semaphore 比在每个 ThreadPool 处加更干净。

**验收**：并发压测下无 429 连锁；`[PROFILE]` 无"僵尸 + 组写作叠加"导致的 2502s。

---

## 三、第三刀升级：稳定前缀 + 动态后缀（顺带吃缓存命中）

**现状**：每个维度 prompt 全量拼注入块（诚实评估：8-12K/维度）。按维度切片到 2-4K 是第一步；但要同时拿到 **provider 缓存命中**，需把 prompt 拆成：

```
稳定前缀（每次相同）: system + SAC 维度定义 + 数据锚卡 + 合规 + 全局方法论规则
动态后缀（每维度不同）: 该维度的 KB/MKB 注入子集 + 数据/图表引用 + 维度专属指令
```

**为什么重要**：稳定前缀命中 provider 侧 prompt cache（Anthropic/DeepSeek 缓存读 token 便宜 ~90%）——**token 变少 + 缓存命中是叠加收益**，不是二选一。诚实评估只算了"token 变少"，漏了缓存这一层。

**关键约束（与 KB 落地联动）**：维度注入子集**必须保留该维度应引用的 KB 条目**——否则"压缩"又把方法论赶出报告（本轮 KB 引用门禁 `kb_citation_coverage` 刚接线）。DIMENSION_INJECTIONS 映射表要与 KB 检索维度 tag 对齐，且被压缩掉的条目不计入引用覆盖率分母。

**实现**：`section_writer._build_prompt_v4` / `_write_dimension_parallel` 的 prompt 拼装重构为"前缀常量 + 后缀变量"；前缀缓存键稳定（不随时间/attempt 变）。

**验收**：provider 缓存命中率可观测（DeepSeek 账单缓存项）；KB 引用覆盖率不降（门禁守）。

---

## 四、新增第四刀：cascade——只深化失败维度（收敛"调用次数"）

**现状**：骨架模式后，深化仍是整组全量重写；attempt>0 有 `rewrite_indices` 段级重写（已好），但**首轮 20-50 次 LLM 调用**这个 2-3x 差距没动。

**顶级实践（cascade / best-of-N / hybrid-model-router）**：
1. **骨架用便宜模型**（opencode_go/本地）出结构 + 关键数字 + Bold Call；
2. **深化只针对 Gate 标红维度**：贵模型（deepseek）只深化 `failed_dimensions`，通过维度**复用骨架**——不是整组深化；
3. **对侧校验分离**：本地/免费模型当 critic（已有 `critic_panel`），DeepSeek 只做主写 + 终审。

**收益**：调用次数 20-50 → 15 内；重试轮 1.5-2 → 0-1（因为首轮就把"哪些维度要深化"定准）。

**依赖**：需要"维度级 Gate 反馈"（诚实评估第四刀已在列表）——两者结合：Gate 反馈维度化 → cascade 只改标红维度。

---

## 五、执行路线（升级版，替代诚实评估 §五）

```
第一刀（确定性、零风险，0.5-1 天）：
  分层超时：llm_connect_timeout_s + 节点级 read 档位（research 30 已好 / 写作 60-90 / merge 45）
  → 重尾 max 从 5-13 分钟砍到 <90s；不改 prompt、不改逻辑

第二刀（观测闭环，0.5 天）：
  merge/自愈段级日志（诚实评估已部分做）+ [PROFILE] 补 connect vs read 超时分类
  → 拿到"超时 vs 慢响应"分布，决定自适应参数

第三刀（全局并发闸，0.5-1 天）：
  core/llm_concurrency.py semaphore + call_llm 包一层 + 熔断 open 即 fail-fast
  → 消除"僵尸 + 组写作叠加"的 429 雪崩与 2502s 极值

第四刀（最大杠杆，1-2 天，需 KB 门禁稳定后）：
  稳定前缀 + 动态后缀（按维度注入子集 + 保 KB 引用）
  → token 减半 + 缓存命中叠加；LLM 处理时间砍半

第五刀（终局，条件性）：
  Gate 反馈维度化 + cascade 只深化失败维度
  → 调用次数 20-50 → 15 内，重试 1.5-2 → 0-1
```

---

## 六、与现有文档关系

| 文档 | 关系 |
|---|---|
| PIPELINE_ACCELERATION_HONEST_ASSESSMENT_20260907.md | 本升级版是它的执行路线的**机制补强**（三刀升级 + 加 cascade 一刀） |
| PIPELINE_ACCELERATION_REVISED_20260907.md | 真实 PROFILE 优先级（本版执行它的 P0-3 重尾熔断的具体化） |
| PIPELINE_ACCELERATION_ANALYSIS_20260907.md | 原方案（已被两版修正取代） |
| FIX_REPORT_research_planner_budget / section_profile | 已落地的基础（本版在其上叠加） |

---

## 七、一句话结论

> 诚实评估的"先止血→再观测→再压缩→再路由"方向是对的；顶级解法把每步的机制补强为——**超时要分层自适应、僵尸线程要用全局 semaphore 限并发而不是试图杀、按维度注入要拆稳定前缀吃缓存命中、以及用 cascade 只深化失败维度来收敛调用次数**。前四刀确定性、零质量损失；第五刀是终局杠杆。落地顺序：分层超时 → 观测 → 并发闸 → 前缀缓存 → cascade。
