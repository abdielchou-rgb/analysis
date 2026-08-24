# R66 柯力传感写作失败修复简报

> 修复日期：2026-08-04 ｜ 依据：`D:\Marvis\output\柯力传感写作失败深度分析_20260804.md` ｜ 状态：四重根因全修，61 回归全绿

---

## 一、核实结论：Marvis 分析完全属实

柯力 run2 三轮 attempt 全被 IronGate 拦截（Gate 0.81→0.80→0.77），**attempt1 高质量稿被 attempt3 全量重写覆盖成泛化行业稿**（真实营收 10.72 亿写成 3.6 亿、对标 NVIDIA/Apple、残留"端侧变现"模板句），且系统全程未感知退化。四重根因逐一代码证实：

| # | 根因 | 代码证据 | 危害 |
|---|---|---|---|
| 1 | **score 读取 bug** | `e2e_orchestrator` L836/L1218 用 `gate.get("score")`，但 `GateReport.to_dict` 字段是 `overall_score` | 分数恒 0 → 回归/stalled 检测全失效，退化不可见 |
| 2 | **charts 失败短路全量重写** | `_locate_failed_segments` 的 charts 分支在 R53 分离逻辑前 `return None` | 每轮重新掷骰子，SAC 13→18→13 无收敛 |
| 3 | **enrich 注入断裂** | `_serialize_data` 对 `fig_*` 键只列键名不注数值 | LLM 拿不到真实数据 → 靠模型记忆写作 → 编造 |
| 4 | **无 best-so-far** | attempt 间无回滚机制 | attempt3 覆盖 attempt1 好稿 |

---

## 二、修复内容（4 项）

| 优先级 | 修复 | 改动 |
|---|---|---|
| **P0** | score 读取 bug | e2e 两处 `gate.get("score")` → `overall_score`（带 fallback），恢复回归/stalled 检测 |
| **P1** | charts 失败改局部重写 | charts 分支返回**全段局部重写**（补图引用），不再短路全量重写 |
| **P1** | best-so-far 稿保留 | attempt 循环记录最高分稿，失败时回滚写回 `_gate_prev.md` |
| **P0** | enrich 数据注入 | `_serialize_data` 对 `fig_*` 键注入具体数值（截断 600 字），LLM 拿到真实数据 |

---

## 三、验证

- 新增 `tests/test_r66_keli_fix.py` 5 项（score 读取/charts 不短路/best-so-far/enrich 注入/语法）
- **61/61 回归全绿**（r66 + r65/r62/engineering_plan/r60/fp_valuation/consistency/ratio/r58）

---

## 四、深层教训

1. **"字段名不匹配"类 bug 是最隐蔽的失败放大器**——系统"看起来在跑"，但所有基于该字段的决策全失效。R61 迁移改了 `GateReport.to_dict` 字段，调用方未同步。
2. **全量重写 = 掷骰子**——只要 LLM 质量随机，全量重写必然无收敛。局部重写 + best-so-far 是标配。
3. **数据进不了正文 = 靠模型记忆**——enrich 数据存在但 LLM 拿不到，就会编造。数据注入链路必须端到端验证。

---

## 五、遗留（P2，未阻断）

- DeepSeek 不可用时 fallback 到 agent_provider 的质量随机性（需显式接受该 provider 并做质量护栏，或修 DeepSeek）
- SELF_AUDIT BOM 问题（`em_host_test.py` U+FEFF）
- COMPLIANCE "反方观点存在"失败项三轮不变，未纳入修订目标

---

*修复已沉淀 memory `2hao-r66-keli-write-fix.md`。*
