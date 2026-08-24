# 性能模式综合工程计划（2026-08-02）

> 前置：训练模式慢的根因已定位（无效重跑/改报告不生效/Marvis串行）。
> 本文档：对性能模式做冒烟测试，验证是否存在类似问题，综合网上顶级打法形成工程计划。
> 冒烟测试时间：2026-08-02

---

## 一、冒烟测试结果（性能模式）

### 1.1 SQLite 并发写锁（R48 统一连接层）

```
10 线程 × 20 写 = 200 行（期望 200）
耗时 0.01s，0 锁错误，journal_mode=wal
```

**结论**：✅ 通过。多报告并发写 financials.db 不再 `database is locked`。

### 1.2 数据跨 attempt 复用（性能模式核心）

```
e2e_orchestrator.py:1140  [CACHE] 首轮采集数据已缓存（%d keys），后续重试轮复用
e2e_orchestrator.py:184   [DATA] 复用缓存采集数据（attempt>0）
```

**结论**：✅ 通过。性能模式**不会**像训练模式那样每轮重跑网络采集——首轮缓存、重试轮复用。

### 1.3 REVISE-LOCAL 失败定位

```
处理三类失败：
  SAC 维度缺失 → 定位到所属段
  图表完整性 → 全局问题，返回 None 触发全写
  COMPLIANCE → 定位到判断段
```

**结论**：⚠️ 部分。SAC/图表/合规三类已覆盖，但 `content_volume` / `annotation_types` / `排版一致性` 等**全局性失败不在定位逻辑内**——可能定位不到段导致无效重写。

### 1.4 模板图死循环风险

```
Generated 9/12 charts for industry_deep (data=template)
[CHART-FALLBACK] 自动追加 9 张未引用图表
```

**结论**：⚠️ 风险。数据不足时用模板图（`data=template`），但 Gate 的 `chart_completeness` 又要求真实数据 → 可能死循环。这是**双模式共享问题**。

---

## 二、与训练模式共享的 3 个问题（冒烟测试暴露）

| # | 问题 | 训练模式 | 性能模式 | 根因 |
|---|---|---|---|---|
| 1 | **改报告不生效**（失败项不变） | ✅ 已确认（3轮同失败） | ⚠️ 同机制风险 | REVISE-LOCAL 不覆盖全局性失败 |
| 2 | **模板图死循环** | ✅ 已确认 | ⚠️ 同风险 | 数据不足时 template 图 vs chart_completeness |
| 3 | **数据采集冗余** | ✅ 已确认（每轮重采） | ✅ 已修复（缓存复用） | 训练模式缺缓存接线 |

---

## 三、网上顶级打法（对标）

### 3.1 改报告不生效 → 跨迭代传递发现 + 去重

| 打法 | 来源 | 要点 |
|---|---|---|
| **跨迭代传 prior findings + 去重** | [stevegrocott/claude-pipeline #11](https://github.com/stevegrocott/claude-pipeline/issues/11) | 质量循环收敛必须传"上轮已修什么"，去重避免同一问题反复 |
| **减少质量循环空转（churn reduction）** | [stevegrocott #50](https://github.com/stevegrocott/claude-pipeline/issues/50) | 分析哪些迭代是无效的，上轮失败=本轮失败时提前终止 |
| **自动收敛循环** | [oss-autopilot #480](https://github.com/costajohnt/oss-autopilot/pull/480) | 修复后自动重跑直到通过，失败项不变时换策略 |

### 3.2 数据采集冗余 → 缓存推理

| 打法 | 来源 | 要点 |
|---|---|---|
| **SemanticALLI：缓存推理非响应** | [arXiv 2601.16286](https://scirate.com/arxiv/2601.16286) | agentic 系统缓存推理过程，相同问题不重复推理 |
| **Redis agent pipeline 缓存** | [Redis AI blog](https://redis.io/blog/ai-agent-pipeline.md) | 中间产物（数据/图表/计算）跨运行复用 |

### 3.3 Marvis 串行 → 并行度

| 打法 | 来源 | 要点 |
|---|---|---|
| **非线性成本** | [O'Reilly](https://www.oreilly.com/radar/linear-thinking-nonlinear-costs/) | LLM 管线延迟非线性，串行步骤指数放大 |
| **质量循环结构性重构** | [inference-sim #430](https://github.com/inference-sim/inference-sim/issues/430) | 循环不收敛时结构性重设计，非打补丁 |

---

## 四、工程计划（分 3 期）

### 第一期（P0）：收敛机制（双模式共享）

| # | 任务 | 说明 | 受益 |
|---|---|---|---|
| 1 | **REVISE-LOCAL 覆盖全局性失败** | content_volume/annotation_types/排版 → 返回 None 触发全写 + 明确提示 | 改报告生效 |
| 2 | **失败项变化检测** | 上轮失败 = 本轮失败 → 提前终止或换策略（补数据/换provider/降级） | 避免无效重跑 |
| 3 | **state_anchor 记录已修项** | 每轮记录"已修 X"，下轮 prompt 明确"只剩 Y" | 收敛加速 |

### 第二期（P1）：数据/图表面板

| # | 任务 | 说明 | 受益 |
|---|---|---|---|
| 4 | **模板图豁免** | `data=template` 时 chart_completeness 降级为 warning，或明确标注"示意" | 打破死循环 |
| 5 | **训练模式 data_feeds 缓存接线** | 把性能模式的缓存复用逻辑接到训练模式 | 每轮省 30 秒 |
| 6 | **缓存推理** | data_feeds/charts 中间产物跨运行缓存（SemanticALLI 思路） | 降低重复计算 |

### 第三期（P2）：并行度优化

| # | 任务 | 说明 | 受益 |
|---|---|---|---|
| 7 | **Marvis 多实例并行** | agent_provider 支持多个响应线程，6 组写作并行 | 写作 2分钟 → 40秒 |
| 8 | **收敛判定指标** | 记录每轮失败数/分数趋势，达平稳则收敛 | 可观测 |

---

## 五、验收标准

| 指标 | 当前 | 目标 |
|---|---|---|
| 气体传感器 3 轮收敛 | 3 轮同失败（无效） | ≤2 轮收敛到通过或明确失败 |
| 训练模式单轮耗时 | ~10 分钟 | ≤5 分钟（去掉无效重跑） |
| 性能模式多报告并发 | 无锁死（已通过） | 保持 + 数据复用 |
| 模板图死循环 | 存在风险 | 打破（豁免或标注） |

---

## 六、优先级判断

**最高价值：第一期 #1+#2（REVISE 覆盖全局 + 失败项变化检测）**
- 直接解决"3 轮无效重跑"——这是训练模式慢的主因
- 性能模式同样受益（改报告更精准）
- 对标 stevegrocott 的"prior findings + churn reduction"，改动集中

**次高：第二期 #4（模板图豁免）**
- 打破双模式共有的死循环风险
- 数据不足时不再被 chart_completeness 卡死

---

*冒烟测试 + 顶级打法对标 + 3 期工程计划。核心：让质量循环"记住已修"，不做重复功。*
