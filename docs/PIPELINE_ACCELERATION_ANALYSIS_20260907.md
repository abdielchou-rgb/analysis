# 二号分析师 · 管线加速分析与顶级解法

> 日期：2026-09-07
> 基线：单份报告 ~270s（E2E Orchestrator），LLM 写作占 60-70%
> 目标：零质量损失下降 30-45%，有条件下降 50%+

---

## 0. 管线瓶颈定位

### 0.1 当前 DAG 拓扑

```
preflight ──→ biz_macro ──→ data ──→ universe_build ──→ enrich ──→ compute ──→┐
                                   └→ data_feeds ───────────────────────────→ │
hypothesis ─────────────────────────────────────────────────────────────────→ │
learning ───────────────────────────────────────────────────────────────────→ │
research_planner (600s timeout) ───────────────────────────────────────────→ │
cross_validate ────────────────────────────────────────────────────────────→ │
argument ──────────────────────────────────────────────────────────────────→ │
scarcity ──────────────────────────────────────────────────────────────────→ │
charts ────────────────────────────────────────────────────────────────────→ write_sections
                                                                            ↓
                                                                    style_compile
                                                                            ↓
                                                                        assemble
                                                                            ↓
                                                                       validate
                                                                            ↓
                                                          review_sections (attempt>0)
                                                                            ↓
                                                         rewrite_sections (attempt>0)
                                                                            ↓
                                                          critic → compliance → export
```

**关键路径**：`data → enrich → write_sections → style → assemble → validate`

### 0.2 耗时分布（典型茅台报告实测）

| 阶段 | 节点 | 耗时 | 占比 | 瓶颈类型 |
|---|---|---|---|---|
| Harness | preflight | ~19s | 7% | I/O |
| 数据采集 | data + enrich | ~30-60s | 11-22% | I/O（网络） |
| 计算 | compute | ~15-30s | 6-11% | CPU |
| 图表 | charts | ~10-20s | 4-7% | CPU |
| **LLM 写作** | **write_sections** | **~120-200s** | **44-74%** | **I/O（LLM API）** |
| 样式 | style_compile | ~5-10s | 2-4% | CPU |
| 装配 | assemble | ~3-5s | 1-2% | CPU |
| 门禁 | validate | ~5-10s | 2-4% | CPU |
| 审稿+重写 | review+rewrite | ~60-120s | 22-44% | I/O（attempt>0） |

**结论**：LLM 写作是绝对瓶颈（占 44-74%），数据采集是第二瓶颈。

---

## 1. 十大加速方案

### ① 数据采集+计算节点并行化（P0，省 30-60s，零质量损失）

**现状**：`data → enrich → compute/charts` 严格串行。但 `data_feeds`、`hypothesis`、`learning` 节点依赖很轻或为空。

**优化**：利用 AgentGraph 已有的拓扑并行能力，把独立节点提前启动。

```python
# 现在（串行关键路径）
data(30s) → enrich(20s) → compute(20s) → write
                                  → charts(15s) → write

# 优化后（四路并行）
data(30s) → enrich(20s) → compute(20s) ──→ write
hypothesis(5s) ───────────────────────────→ write
learning(3s) ─────────────────────────────→ write
charts(15s, 提前启动) ───────────────────→ write
```

**实现方式**：
1. 在 `agent_graph.py` 中调整 `add_node` 的 `deps` 声明
2. `charts` 节点改为 `deps=["data"]`（不等 `enrich`）
3. `compute` 节点改为 `deps=["data"]`（只要有 revenue 就启动）
4. `hypothesis`/`learning` 已是 `deps=[]`，确认无隐式依赖

**风险**：零。各节点读同一 `ctx`，写不同 key，无竞态。

---

### ② Prompt 压缩 / 按维度动态注入（P0，省 40-60% LLM 延迟）

**现状**：每个维度写作 prompt 包含全量注入块：
- KB 参考：1500 chars
- MKB 方法论：2000 chars
- 证据清单：40 条
- 宏观背景：全文
- KG 同业：全文
- 合计：~8000-12000 tokens

**问题**：维度 1（商业模式）不需要 DCF 敏感性矩阵；维度 5（估值）不需要竞争格局表格。全量注入浪费 prompt 空间 + 增加 LLM 处理时间。

**顶级解法**（业界实践）：

| 方案 | 原理 | 效果 | 适用性 |
|---|---|---|---|
| **LLMLingua-2**（Microsoft） | 小模型判断 token 重要性，压缩 2-5x | 保留 90%+ 任务性能 | 需要额外模型 |
| **Select-and-Edit** | 按任务选择最相关段落 | 延迟降 40-60% | 最适合本项目 |
| **Contextual Compression** | 根据当前维度动态选择注入子集 | 延迟降 30-50% | 最适合本项目 |

**推荐实现**：按维度分组注入子集

```python
# 现在：每个维度拿到全量注入
 injections = kb_str + mkb_str + ev_str + macro_str + kg_str

# 优化后：每个维度只拿相关注入
DIMENSION_INJECTIONS = {
    "business_model":  ["kb_competitive", "mkb_valuation", "ev_figures"],
    "financial":       ["kb_financial", "mkb_accounting", "ev_figures", "compute_results"],
    "valuation":       ["kb_valuation", "mkb_dcf", "compute_results", "kg_peers"],
    "risk":            ["kb_risk", "macro_str", "policy_str"],
    # ... 其他维度
}
```

**风险**：中等。需要维护维度→注入映射表，新增维度时需同步更新。

---

### ③ 异步 LLM 调用（P0，省 20-40% 等待时间，零质量损失）

**现状**：`write_sections` 用 `ThreadPoolExecutor` 做维度并行：

```python
with ThreadPoolExecutor(max_workers=5) as ex:
    futures = [ex.submit(_write_one_dimension, dim) for dim in dims]
```

**问题**：Python ThreadPool 有 GIL 争用 + 线程切换开销。LLM 调用是纯 I/O，asyncio 更高效。

**优化**：

```python
import asyncio

async def write_all_dimensions(dims, prompts):
    tasks = [_write_one_dimension_async(dim, p) for dim, p in zip(dims, prompts)]
    return await asyncio.gather(*tasks)

# asyncio vs ThreadPool 性能对比（I/O-bound 场景）
# asyncio:  无 GIL 争用，无线程切换，延迟降 30-50%
# ThreadPool: 有 GIL 争用，线程切换 ~10-50μs/次
```

**实现步骤**：
1. LLM 客户端包装为 async（`aiohttp`/`httpx.AsyncClient`）
2. `write_sections` 改为 `async def`
3. AgentGraph 节点调用时用 `asyncio.run()` 包装

**风险**：零。纯 I/O 并发优化，不改 prompt/逻辑。

---

### ④ Provider 链智能路由（P0，省 30-120s 延迟，零质量损失）

**现状**：provider 按固定顺序 fallback：`opencode_go → deepseek → zhipu → openrouter → zen → ollama → agent_provider`。每个 fallback 要等超时才切换。

**优化**：

```python
# 方案 A：预探测（每次运行开始 ping 所有 provider）
async def probe_providers():
    """并行 ping 所有 provider，返回延迟排序。"""
    results = await asyncio.gather(*[
        ping_provider(p) for p in all_providers
    ])
    return sorted(results, key=lambda x: x.latency)

# 方案 B：维度级路由
# 骨架用免费模型，深化用付费模型
PROVIDER_ROUTING = {
    "skeleton": "opencode_go",      # 免费，快速
    "deepen":   "deepseek",         # 付费，高质量
    "review":   "deepseek",         # 审稿需要高质量
}

# 方案 C：超时熔断
# 单个 provider 超时 10s 立即切换，不等 30s
TIMEOUT_PER_PROVIDER = 10  # 秒
```

**风险**：零。只是选择更快的 provider，不改输出质量。

---

### ⑤ LLM 响应缓存（P1，省 50-80% 重试延迟）

**现状**：写改循环（attempt 0→1→2）每次重写全量维度。但 prompt 80% 相同（只有 gate_feedback 不同）。

**优化**：对维度级 LLM 调用做 prompt hash 缓存

```python
import hashlib

def prompt_hash(dim_id: str, data_hash: str, gate_feedback_hash: str) -> str:
    """prompt 的稳定 hash——数据不变 + 反馈不变 = 复用缓存。"""
    return hashlib.md5(f"{dim_id}:{data_hash}:{gate_feedback_hash}".encode()).hexdigest()

# 缓存策略
if gate_feedback 变化 ≤20%:
    复用上一轮维度结果（只改 feedback 相关段落）
else:
    全量重写
```

**实现**：Redis 或本地 JSON 文件，TTL = 1 小时。

**风险**：低。需要确保 gate_feedback 变化检测准确。

---

### ⑥ Skeleton + Deepen 双阶段（P1，省 40-60% 首轮延迟）

**现状**：`skeleton_mode` 只对 `industry_deep` 启用。且骨架→深化的切换是全文重写。

**优化**：扩展到所有报告类型 + 精准深化

```
阶段1: 快速模型（opencode_go/ollama_local）出骨架
  └→ 结构 + 关键数字 + Bold Call + 风险
  └→ 通过 Gate 结构检查

阶段2: DeepSeek 深化（只改写 quality 不达标的段落）
  └→ Gate 反馈精确到维度级
  └→ 只重写 flagged 的维度
  └→ 其余维度复用骨架
```

**关键改进**：当前 skeleton→deepen 是全文重写，优化后只改写不达标的段落。

---

### ⑦ Gate 反馈精准化（P1，省 1-2 轮重试）

**现状**：Gate 反馈是全文级别的（`"覆盖不足，需要补充行业分析"`），LLM 改写时不知道具体改哪里。

**优化**：维度级 Gate 反馈

```python
# 现在
gate_feedback = "SAC覆盖率68%，需要补充行业分析和风险评估"

# 优化后
gate_feedback = {
    "failed_dimensions": [
        {"id": "competitive_landscape", "issue": "缺少CR3数据", "severity": "error"},
        {"id": "risk_analysis", "issue": "缺少政策引用", "severity": "warning"},
    ],
    "passed_dimensions": ["business_model", "financial", "valuation", ...],
}
```

LLM 改写时只改 flagged 的维度，其余复用上一轮。

---

### ⑧ 计算预热（P2，省 10-20s）

**现状**：`compute` 节点等 `enrich` 完成后才启动。但 DCF 只需要 `revenue/margin/WACC`，这些在 `data` 节点就有了。

**优化**：`compute` 节点改为 `deps=["data"]`，只要有 revenue 数据就启动。`enrich` 完成后补充 backfill 数据。

---

### ⑨ 图表预生成（P2，省 15-30s）

**现状**：`charts` 节点等 `enrich` 完成后才启动。但 `fig_revenue_trend`、`fig_valuation` 在 `data` 节点就有了。

**优化**：`charts` 节点改为 `deps=["data"]`，`enrich` 完成后只更新增量图表。

---

### ⑩ 维度分组优化（P2，省 10-20% LLM 调用）

**现状**：维度分组是固定的。共享上下文多的维度可能被分到不同组，导致重复注入。

**优化**：按 prompt 相似度动态分组

```python
def group_by_prompt_similarity(dimensions):
    """共享注入块 > 60% 的维度放一组，减少重复注入。"""
    # 估值 + DCF + 可比 → 一组（共享 compute_results）
    # 商业模式 + 竞争格局 → 一组（共享 kg_peers）
    # 风险 + 政策 → 一组（共享 macro_str）
```

---

## 2. 组合效果预估

| 方案组合 | 预估总耗时 | 降幅 | 实现周期 |
|---|---|---|---|
| ①+⑤+⑥（零风险三件套） | ~150-180s | 30-45% | 1-2 天 |
| ①+②+⑤+⑥（含 prompt 压缩） | ~100-140s | 48-63% | 3-5 天 |
| 全部 P0（①+②+③+④） | ~90-130s | 52-67% | 3-5 天 |
| 全部 P0+P1 | ~70-100s | 63-74% | 5-7 天 |

---

## 3. 与业界对标

| 指标 | 二号分析师（当前） | 顶级投行研报系统 | 差距 |
|---|---|---|---|
| 单份报告时间 | 5-15 min | 1-3 min（人工+工具） | 2-5x |
| LLM 调用次数 | 20-50 次 | 5-15 次 | 2-3x |
| Prompt token 量 | 8-12K/维度 | 2-4K/维度 | 2-3x |
| 重试轮数 | 1.5-2 轮 | 0-1 轮 | 1.5-2x |
| 数据采集 | 30-60s | 5-15s（缓存） | 2-4x |

**最大差距**：prompt token 量（本项目 8-12K vs 业界 2-4K）—— 解法是 ② 按维度动态注入。

---

## 4. 质量保障约束

加速不能牺牲质量。以下红线不可突破：

1. **SAC 维度覆盖率 ≥70%** — prompt 压缩不能丢维度相关内容
2. **数据来源标注率 ≥30%** — 证据注入不能压缩
3. **IronGate 101 项检查全过** — 加速后必须重跑门禁
4. **So-What 链每段必须有** — 写作逻辑不能简化
5. **目标价+评级+催化剂必须包含** — 核心输出不能省略

建议：每个加速方案上线前，先用固定 seed prompt 跑 before/after 对比，确认 Gate score 不降。

---

## 5. 推荐执行路线

```
第1天：① 节点并行化 + ⑥ Provider 路由（零风险，立竿见影）
第2天：③ 异步 LLM 调用（零风险，ThreadPool→asyncio）
第3天：② 按维度动态注入（中风险，需维护映射表）
第4-5天：⑦ Gate 精准化 + ⑤ 响应缓存（中风险，需测试）
第6-7天：④ Skeleton+Deepen + ⑧⑨⑩（低风险收尾）
```

---

## 6. 一句话

> **最大杠杆是"按维度动态注入 prompt"（②）—— 把 8-12K token 的全量注入压缩到 2-4K，LLM 处理时间直接砍半。其次是"异步 LLM + Provider 路由"（③+④）—— 零质量损失的 I/O 优化。两者组合可将管线从 ~270s 降到 ~100-130s（降幅 52-63%）。**
