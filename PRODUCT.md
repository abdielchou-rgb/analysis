# 二号分析师 — 产品说明

> **意图驱动的智能分析系统**：回答委托方的必答问题，而非生成一份"看起来完整"的报告。

## 产品定位

2hao 是把投资银行（问题驱动）、MBB 咨询（假设驱动/问题树/金字塔）、四大审计（专业怀疑/分析性程序）的方法论，工程化为可复用的 AI 分析引擎。

**核心洞察**：传统管线（SAC 模板 → LLM 生成 → Gate 校验）的每层都在压缩用户意图——最终报告"结构正确但没回答用户的问题"。2hao V2 用 **FP0 意图第一公民** 解决这个问题：报告结构由必答问题驱动，Gate 校验"答没答对题"。

## 三种执行路径（FP8 光谱架构）

```
批量/标准化 ────────→ 确定性管线（E2E+SAC+IronGate）
深度/个性化 ────────→ 工作台混合（数据层+AI直接写+用户审核）
高险决策文档 ────────→ 工作台+强制人类门禁+双向溯源
```

路径由 `task_router` 自动选择，两条路径共享数据层/校验层/记忆层。

## 设计哲学

1. **人定意图、AI 写、代码算、工具校验、记忆纠偏**（人机协作工作台）
2. **把 AI 的自由度限制在它擅长的事**（组织语言/推演逻辑），把算术/事实/一致性交给代码和工具，把最终判断交给人
3. **幻觉无法消除，但能被隔离**——长文中 AI 最易幻觉的三类（数字算术/事实记忆/跨章节一致性）全部用确定性手段兜底

## 同行方法论的工程化落地

| 同行 | 方法论 | 2hao 落地 |
|------|--------|-----------|
| MBB | 假设驱动 | `hypothesis_driven.yaml` + 决策引擎先出假设 |
| MBB | 问题树（MECE） | `issue_tree.yaml` + SAC 意图映射 |
| 芭芭拉·明托 | 金字塔原理 | `pyramid_principle.yaml` + 执行摘要先行 |
| 四大 | 专业怀疑 | IS-CoT 反思升级（写手默认假设可能有错） |
| 四大 | 分析性程序 | `data_caliber` 数据矛盾检测 |
| 投行 | 客户问题第一 | `intent_parser` 必答问题清单 |
| Stanford | DSPy 编译式 | `context_compiler` 参数化上下文生成 |

## 适用场景

- **决策备忘录**：老板要拍板（进/不进/条件性进），评估市场规模/投入产出/战略卡位
- **单份深度研究**：个性化问题，非标准模板
- **批量跟踪报告**：定期批量出报告，标准化
- **非上市尽调**：可比融资/治理/退出路径深化

## 快速验证

```bash
# 1. 意图解析（FP0）
python -c "from core.intent_parser import IntentParser; p=IntentParser().parse('X','decision_memo','评估市场规模/投入产出比'); print(p['must_answer_questions'])"

# 2. 任务路由（FP8）
python -c "from core.task_router import route_task; print(route_task('decision_memo','评估投入产出'))"

# 3. 代工测算
python -c "from core.compute.contract_manufacturing import calculate_contract_manufacturing as c, format_summary as f; print(f(c({'capacity_units':50000,'unit_price':2000,'variable_cost':1400,'fixed_capex':30000000,'fixed_opex_year':5000000})))"

# 4. 端到端工作台
python -m core.workbench_executor "柯力传感" --type decision_memo --requirement "评估市场规模/投入产出比" --human-gate
```

## 关于本产品

- **不是**：一个 prompt 包装器、一个"多 agent 评审"玩具
- **是**：把顶级机构几十年沉淀的隐性规则，显性化为可复用、可验证、可演化的 AI 分析系统
- **核心资产**：FP0 意图宪法 + 光谱架构 + 计算模块 + 事实库 + 质量门禁 + 三通道路由

---

*License: MIT*
