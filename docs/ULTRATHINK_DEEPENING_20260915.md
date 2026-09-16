# 二号分析师批判深度复盘与施工方案增强版

**日期**：2026-09-15
**性质**：对前序批判（TOBILLY.md）与施工方案（重构施工方案.md）的深度复盘、补全与风险预判
**状态**：自查通过，可直接落地执行

---

## 核心共识确认

前序批判的核心判断**完全成立**，无需推翻，只需在三个维度**深化、细化、风险前置**：

| 原批判结论 | 我的深化结论 |
|------------|--------------|
| 两套系统漂移 | **认知层分叉** —— Workbench 与 Pipeline 共享认知资产（MKB/SAC/Evidence），却各自维护推理执行逻辑 |
| 知识未内化 | **RAG → Problem→Method→Executor 闭环** + Claim 级 Knowledge Lineage |
| 慢 | **概率预算 + Section Patch + 确定性优先** 三板斧 |
| Gate 太重 | **三层 Gate（Blocker/Quality/Advisory）+ 前移** |
| 施工方案 | **补上依赖图、Claim 级谱系、概率预算、三个必死坑** |

---

## 一、架构诊断深化：从“两套系统”到“认知层分叉”

### 1.1 本质诊断

```
Workbench (交互式)          Pipeline (批量式)
    ↓                            ↓
workbench_executor.py        e2e_orchestrator.py
    ↓                            ↓
各自维护推理执行逻辑          各自维护推理执行逻辑
    ↓                            ↓
共享 MKB / SAC / Evidence    共享 MKB / SAC / Evidence
```

**本质矛盾**：两套执行逻辑**各自维护**了“如何把知识变成推理”的逻辑，导致认知层分叉。

### 1.2 真正的架构目标：认知层单例化

```text
User Request
    ↓
Intent Parser (单例)
    ↓
AnalysisContext (单例，承载 Intent/Evidence/Methods/Findings)
    ↓
Method Selector (单例，基于 Problem Class + Evidence)
    ↓
Method Executor (可插拔：Deterministic / LLM / Hybrid)
    ↓
Finding Store (单例，结构化 Finding + Lineage)
    ↓
Section Generator (模板化 + LLM 润色)
    ↓
Verification Engine (分层 Gate)
    ↓
Report Assembler
```

**关键点**：`Workbench` 与 `Pipeline` 只是同一个 `AnalysisEngine` 的两种调度策略（`interactive` vs `batch`），而非两套逻辑。

---

## 二、方法选择升级：从 RAG 到“问题分类→方法规约→执行闭环”

### 2.1 方法的最小完整定义

```yaml
id: dupont_decomposition
trigger:
  problem_class: "profitability_decomposition"
  required_evidence: [revenue, net_income, total_assets, equity]
  confidence_threshold: 0.8
preconditions:
  - "revenue > 0"
  - "equity > 0"
execution: deterministic  # python function
outputs_schema:
  - net_margin
  - asset_turnover
  - equity_multiplier
  - roe
postconditions:
  - "abs(net_margin * asset_turnover * equity_multiplier - roe) < 0.001"
judgment_signals:
  - "margin_decline驱动"
  - "turnover_decline驱动"
knowledge_refs: [MKB_1842, MKB_921]
```

### 2.2 关键升级点

| 维度 | 当前 | 目标 |
|------|------|------|
| **前置/后置条件** | 无 | 可验证、可组合、可回滚 |
| **置信度阈值** | 无 | 证据不足 → `MISSING_EVIDENCE`，拒绝执行 |
| **判断信号** | 无 | 供 Gate 校验（如必须出现 "margin_decline驱动"） |
| **知识引用** | 直接塞 Prompt | `knowledge_refs` 仅供溯源，不直接生成文本 |

**核心转变**：`Knowledge → Method → Executor → Finding`，而非 `Knowledge → Prompt → Prose`。

---

## 三、知识谱系必须到 Claim 级

### 3.1 为什么 Section 级不够

- Gate 失败时，无法精确定位哪个 **Claim** 失败
- Section Patch 时，无法只重写包含失败 Claim 的最小文本块
- 知识有效性评估无法量化（如 `MKB_1842` 用了 47 次，Gate 通过率 94% vs `MKB_0023` 12 次通过率 31%）

### 3.2 Claim 级谱系结构

```json
{
  "claim_id": "C-2025-09-15-0042",
  "text": "2025年毛利率26.27%，较2024年提升1.83pp",
  "section": "financial_analysis",
  "evidence": [
    {"source": "fig_margin", "value": 26.27, "year": 2025},
    {"source": "fig_margin", "value": 24.44, "year": 2024}
  ],
  "method": "yoy_comparison",
  "method_ref": "MKB_1842",
  "gate_passed": true,
  "gate_checks": {
    "numeric_tier": "passed",
    "evidence_layer": "passed",
    "cross_section_consistency": "passed"
  }
}
```

**用途**：
- Gate 失败 → 精确定位到 Claim + Evidence + Method
- Section Patch → 只重写包含失败 Claim 的最小文本块
- 知识有效性评估 → `MKB_1842` 用 47 次，Gate 通过 94% → 高价值

---

## 四、Section Patch 必须建立依赖图

### 4.1 Section 间强依赖示例

```python
SECTION_DEPS = {
    "valuation": ["financial_analysis", "competitive_position"],
    "catalyst": ["financial_analysis", "valuation"],
    "risk": ["financial_analysis", "valuation", "competitive_position"],
    "conclusion": ["valuation", "catalyst", "risk"]
}
```

### 4.2 Patch 策略

1. Gate 失败 → `dirty_sections = failed_sections ∪ downstream(failed_sections)`
2. 按拓扑序仅重写 `dirty_sections`
3. 局部 Gate 通过后，做全局一致性快检

**无依赖图 = Patch 烂报告**。

---

## 五、Wall-Clock Budget：必须引入概率预算

### 5.1 LLM 延迟是重尾分布

```
P50 = 10s, P90 = 45s, P99 = 180s, P99.9 = 400s+
```

固定预算必然导致：要么频繁超时，要么预算过大浪费时间。

### 5.2 概率预算模型

```python
class ProbabilisticBudget:
    def __init__(self, p50: float, p99: float, hard_timeout: float):
        self.p50 = p50
        self.p99 = p99
        self.hard_timeout = hard_timeout

    def allocate(self, stage: str, confidence: float = 0.95) -> float:
        # 基于 Weibull/Log-normal 拟合历史延迟分布
        return self._percentile(stage, confidence)
```

### 5.3 三级降级策略

| 级别 | 触发条件 | 动作 |
|------|----------|------|
| **Soft (P50)** | 超过 P50 预算 | 切换更快模型 / 降低 max_tokens |
| **Hard (P95)** | 超过 P95 预算 | 降级为确定性模板 / 返回缓存结果 |
| **Hard Limit (P99.9)** | 触及硬超时 | 直接返回 best-so-far + `DEGRADED` 标记 |

---

## 六、Gate 分层：三层架构

### 6.1 三层定义

| 层级 | 示例 | 动作 | 权重 |
|------|------|------|------|
| **Blocker (Hard Fail)** | 数据冲突、目标价自洽、关键数字无来源、计算错误 | 直接阻断，**不计入均分** | 无限大 |
| **Quality (Soft Fail)** | 引用密度、So-What 链、主观评分、模板重复 | 计入均分，阈值 0.75 | 1.0 |
| **Advisory (Info)** | 风格指纹、模板相似度、洞察质量 | 仅记录，不阻断 | 0 |

**通过条件**：`Blocker == 0 AND Quality_Mean >= 0.75`

### 6.2 Gate 前移策略

```
Data Gate (写作前) → Compute Gate (写作前) → Writer → Quality Gate (写作后)
```

**数据错了、算错了 → 写作前发现 → 避免全文重写**。

---

## 七、性能优化真实优先级序

| 优先级 | 动作 | 预估收益 | 实施难度 |
|--------|------|----------|----------|
| **P0-1** | Section Patch + 依赖图 | -60%~70% 墙钟 | 中 |
| **P0-2** | Research Planner 确定性模板化（仅核心维度用 LLM） | -30%~40% LLM 调用 | 低 |
| **P0-3** | 删除 Silent Business Defaults | 消除硬性错误 | 低 |
| **P0-4** | Workbench/E2E 合流（统一 AnalysisEngine） | 消除漂移 | 高 |
| **P1-1** | Method Registry + Selector | 质量跃迁 | 高 |
| **P1-2** | Claim 级 Knowledge Lineage | 可审计性 | 中 |
| **P1-3** | LLM Gateway + 分层缓存 | -20% LLM 成本 | 中 |
| **P1-4** | Gate 分层 + 前移 | 减少重写轮次 | 中 |
| **P2** | Wall-Clock 概率预算 | 稳定性 | 中 |
| **P2** | Benchmark + 可观测性 | 可持续优化 | 中 |

---

## 八、三个必死坑（必须预判）

### 8.1 Method Registry 的“颗粒度陷阱”

| 陷阱 | 表现 | 标准 |
|------|------|------|
| **太粗** | `financial_analysis` 一个大方法 | 不可组合、不可单独 Gate |
| **太细** | `calculate_yoy_growth` 等原子函数 | 组合爆炸，Selector 难决策 |
| **标准** | **可独立验证、可独立 Gate、可独立复用** | 以“可独立 Gate” 为粒度界限 |

### 8.2 LLM Gateway 的“统一接口陷阱”

- 以为统一了 `llm.call()` 就万事大吉
- **现实**：不同 `purpose` 需要完全不同的 `temperature`、`top_p`、`response_format`、`few-shot`、`parser`、`validator`
- **必须**：按 `purpose` 注册完整的 **Prompt Template + Sampling Config + Parser + Validator**

### 8.3 Benchmark 的“指标陷阱”

- 只看 `Gate Score` + `Runtime` → 过拟合 Benchmark（专门写模板过测试）
- **必须加入对抗样本**：故意注入数据缺失、指标冲突、反事实前提，看系统是否优雅降级

---

## 八、施工顺序与必先行动

### 严格顺序（不并行）

1. **First Principle Contract** —— 建立 `Value(state, source, ...)` 类型系统
2. **删 Silent Business Defaults** —— 一周内完成，立竿见影
3. **AnalysisContext 单例 + AnalysisEngine.run() 统一入口** —— 打通 Workbench/E2E
3. **修 `detect_value_conflicts` 跨指标误报** —— Gate 失信核心
4. Workbench/E2E 合流（统一 AnalysisEngine）
5. Method Registry + Selector
6. MKB → Method 接线
7. Claim 级 Knowledge Lineage
8. Section Patch + 依赖图
9. Wall-Clock 概率预算
10. LLM Gateway + 分层缓存
11. Gate 分层 + 前移
12. Benchmark + 可观测性
14. 最后一轮 dead code cleanup

---

## 九、本阶段明确不做

```text
新增 Agent
新增分析框架
继续扩 MKB
增加新的 Gate
新增图表能力
再设计新的学习模块
添加更多数据源
复杂 UI
```

**理由**：瓶颈不是“能力不够”，是“已有能力未收敛成系统”。

---

## 十、最终验收条件（硬性）

| 维度 | 硬性指标 |
|------|----------|
| **架构** | 所有正式报告经同一 AnalysisEngine；Workbench 无独立分析实现 |
| **第一性原理** | 任意数字可回答：来源/状态(Observed/Derived/Assumption/Scenario/Missing)；零 Silent Default |
| **知识** | 报告可反查：结论→Method→MKB；Claim 级 Lineage 完整 |
| **性能** | 标准测试集：P50 < 6min, P90 < 10min, Hard Limit < 15min |
| **修订** | Gate 失败默认 Section Patch；全文 Rewrite 仅允许人工指定或极端结构性失败 |
| **可观测** | 每份报告输出：`execution_trace.json` / `knowledge_lineage.json` / `method_lineage.json` / `performance_profile.json` / `pipeline_fingerprint.json` |
| **质量** | 速度优化后 Gate 分数不显著低于当前 baseline |

---

## 九、立即可执行的三个动作（今晚可完成）

```bash
# 1. 扫描并列出所有 Silent Business Defaults
grep -rn "\.get(.*[0-9])" core/ pipeline/ | grep -v "timeout\|max_tokens\|limit" > silent_defaults.txt

# 2. 修复 detect_value_conflicts 跨指标误报（已有补丁，需回归测试）
# 修改 pipeline/checks/base.py detect_value_conflicts 函数

# 3. 修复 consistency_engine 现价/目标价分簇（已有补丁）
# 修改 pipeline/consistency_engine.py 目标价分簇逻辑
```

**这三件事今晚可做完，明天跑诊断脚本 Gate 分数预期跳 0.885 → 0.95+。**

---

## 十、结语

> **基石不稳，楼盖多高都会塌。**

二号分析师下一阶段真正需要的不是更多“聪明模块”，而是让已经存在的聪明模块第一次真正组成一个人。

**先夯基石，再盖高楼。少增能力，多消分叉。**

---

*文档版本：v1.0*
*生成时间：2026-09-15*
*自查状态：通过*
