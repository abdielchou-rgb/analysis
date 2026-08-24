# 偏离框架追溯 — R68 与柯力 v5 决策层违规清单

> 制作日期：2026-08-05 ｜ 基于自查：当前系统偏离了自身框架设计哪些部分，以及为什么会发生

## 一、追溯方法

逐项对照系统自身设计 vs 实际执行结果：

| 维度 | 有没有定义 | 定义在哪里 | 代码有没有注入 | 柯力 v5 有没有出现 |
|------|-----------|-----------|--------------|-----------------|
| **反向 DCF** | 有 | SAC-listed_company: 估值映射维度 sub_question "DCF 估值（含失败概率和国家风险调整）"；section_writer:1500-1514 注入到 prompt | ✅ prompt 中有 | ❌ DOCX 中找不到 |
| **多空逻辑表** | 有 | SAC-listed_company: Bull/Bear Case 是第一步；section_writer:1527-1532 注入 | ✅ prompt 中有 | ⚠️ DOCX 含 "多空" 2 处但无结构化多空表 |
| **预期差分析** | 有 | SAC-listed_company: 估值映射 sub_question "一致预期 vs 我们判断的差距" + section_writer:1500 prompt | ✅ prompt 中有 | ⚠️ DOCX 含 "估值差" 1 处但无 "市场隐含增速 vs 预测增速" 对比 |
| **戴维斯双击/双杀** | 有 | SAC-listed_company: 估值映射 sub_question "戴维斯双击/双杀判断 (EPS方向 × PE方向)" | ✅ prompt 中有 | ❌ DOCX 中找不到 |
| **凯利公式赔率** | 有 | SAC-listed_company: 估值映射 sub_question "赔率评估（潜在涨幅/跌幅比）" | ✅ prompt 中有 | ❌ DOCX 中找不到 |
| **DCF 敏感性 单调性** | 有 | core/compute/compute.py 定义了敏感性与单调性，section_writer 注入到 prompt | ✅ compute 已产出 | ⚠️ DOCX 有敏感性表但结论声称的 "20%" 与分段假设 "9.3%" 矛盾 |
| **催化剂日历** | 有 | SAC-listed_company: 估值映射 sub_question "催化剂日历 (3/6/12 个月事件驱动)"；section_writer:1517-1526 | ✅ prompt 中有 | ⚠️ DOCX 有 "催化剂" 但未按 3/6/12 月结构化 |
| **全局数字注册表** | 部分有 | data_dict 模块有 ref:key 体系 | ⚠️ prompt 中建议使用但 Gate 未强制检查 | DOCX 出现了 5% vs 10% 的口径漂移 |

## 二、为什么会发生——三层根因

### 根因 1：工具数据不进 compute，在 section_writer 末端拼贴

反向 DCF（1500 行）、多空表（1527 行）、催化剂日历（1517 行）——这三个被 R23 定义的 "王牌方法" 全都在 section_writer 的**最末端**执行（`write()` 方法的 1400-1600 行），而不是在 `compute_engine` 中作为正式的 `tool_modules` 计算。

这意味着：
- 它们不在 `_build_tool_modules_injection` 的注入路径中
- `_build_tool_modules_injection` 只覆盖 seg0-2 的 5 个工具（life_cycle/moat/signal_chain/elasticity/multi_model）
- 反向 DCF / 多空表 / 催化剂日历在 prompt 末尾以纯文本形式贴入（`rdcf_str[:1000]`），但工具模块注入是 JSON 截断（`json.dumps(_data)[:400]`），这二者格式不兼容

更致命的是，这些方法的触发条件是 "chart_data 中有 market_cap / fcf 字段"。柯力 enrich 只包含了 fig_revenue_trend/fig_profitability 等原始数据，没有 market_cap/fcf 的结构化字段。所以在柯力v5 的执行路径中，`_sf_extract` 返回 None，反向 DCF/多空表/催化剂日历**全部静默失败**——`except Exception` 被 `logger.debug` 吞掉，系统不知道这些方法没跑。

### 根因 2：SAC 的 "估值映射" 维度定义 vs 实际 prompt 注入的分割

SAC 将估值分解为七个明确的子问题：
1. DCF 估值（含失败概率和国家风险调整）
2. 可比公司估值
3. 敏感性分析
4. TAM vs 财务驱动法交叉验证
5. 戴维斯双击/双杀判断（EPS方向 × PE方向）
6. 赔率评估（潜在涨幅/跌幅比）
7. 均值回归风险（当前估值 vs 历史均值）

但在 section_writer 的实际执行中，这七个子问题是**不区分地混合在同一个 "估值映射" segment 中**写入 `dim_defs` 短语，LLM 需要在同一轮生成中同时完成这七个子问——没有优先级，没有检查清单，没有后续 Gate 验证是否全部完成。

结果是 LLM 选择了最容易的几个：DCF 估值、可比估值、敏感性分析（这三个在 prompt 中最显著）。其余四个——戴维斯双击/双杀、赔率评估、均值回归风险——只是 sub_question 中的一行，LLM 在生成中可以跳过而不触发任何 Gate 拦截。

### 根因 3：section_writer 代码中 18 个"_build"函数的执行顺序

我追查了 section_writer 中所有以 `_build_` 命名的函数的执行顺序和状态：

| 函数 | 行数 | 状态 |
|------|------|------|
| _build_framework_injection | 1380 | ✅ 正常（方法论注入） |
| _build_methodology_injection | 1390 | ✅ 正常 |
| _build_institution_baseline | 1395 | ✅ 正常 |
| _build_cross_report_context | 1339 | ✅ 正常 |
| _build_module_synthesis | 1189 | ✅ 正常 |
| _build_tool_modules_injection | 294 | ✅ 正常（5 工具） |
| _build_forecast (predict_model) | 1419 | ✅ 正常 |
| _build_anti_consensus | 1426 | ✅ 正常 |
| _build_three_statement | 1449 | ✅ 正常 |
| _build_harvard_analysis | 1456 | ✅ 正常 |
| _build_chart_data_injection | 1465 | ✅ 正常 |
| **反向 DCF/隐含预期** | **1500** | ❌ **静默失败**（market_cap/fcf 字段缺失） |
| catalyst_timeline | 1517 | ⚠️ 数据依赖高 |
| bull_bear_matrix | 1527 | ⚠️ 数据依赖高，需 market_cap/fcf/瓶颈/催化剂 |
| unlisted_reverse_valuation | 1538 | ⚠️ 仅 unlisted 类型触发 |
| build_bottleneck_analysis | 1547 | ✅ 正常 |
| build_valuation_crosscheck | 1557 | ⚠️ 状态待查 |
| build_risk_layering_analysis | 1566 | ⚠️ 状态待查 |

这 18 个函数的执行依赖共同的异常处理模式：`try → except → logger.debug → 空字符串`。15 个依赖数据的函数中，只有 12 个能在正常执行中产出结果。反向 DCF 和多空表的失败不是因为代码错误，而是因为**数据链断了**——enrich 不产生 market_cap 和 fcf 字段。

## 三、这意味着什么

回答你的问题：是什么维度缺失、为什么会没有执行到位。

缺失的不是定义——SAC 中有估值映射的全部 7 个子问题。缺失的不是代码——反向 DCF、多空表、催化剂日历的代码全部存在且正常。缺失的是**从数据到工具的链条**。

反向 DCF 需要 market_cap 和 fcf 两个值才能启动二分法求解隐含增速。这两个值不在柯力 enrich 的 fig_revenue_trend / fig_profitability 中。`_sf_extract` 试图从 "chart_data" 或 "fig_peer_comparison" 中找，找不到就返回 None。然后 `except Exception` 被 `logger.debug` 吞掉——这条错误消息的日志级别是 `debug`，在生产环境中根本不可见。

多空表同样是这个路径：bull_bear_matrix 的构建需要 market_cap、fcf、pe、industry_pe、catalyst_timeline——五项数据中 market_cap 和 fcf 不可得，剩余三项可单独提取但不足以支撑完整的反向 DCF 预期差计算，只能退回到默认填充（"行业增长/政策支持"）。

**直接后果**：柯力 v5 的估值结论（60 元）完全依赖正向 DCF 和可比 PE 的推理，没有反向验证。报告的架构设计中要求 "反向 DCF → 找预期差 → 判断市场是否过于乐观"，但实际生成时这个步骤完全未执行。P0-2 的 "隐含增速 20% vs 9.3%" 矛盾正是因为没有 "反向 DCF" 这个制衡力量——若反向 DCF 正常运行，市场隐含增速会被自动算出，报告就不会写出 "隐含复合增速约 20%" 这样的错误。

**深层根因**：系统设计了三层工具——R23 王牌方法（反向 DCF/多空表/催化剂日历）——但它们被设计在**section_writer 的末端**而不是 **compute_engine 的核心计算**中。这使得它们的数据依赖关系脆弱：只要 enrich 不提供市场数据，它们就静默退出。正确的架构应该让 market_cap 和 fcf 作为 compute_engine 的标准产出物，与 elasticity / signal_chain 一样进入 `tool_modules`。
