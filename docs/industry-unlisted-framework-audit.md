# 行业与非上市公司分析——框架丢失与接线缺失审计

> 基于 R68 18 模块全量审计 + SAC 框架对照 + framework_registry 映射
> 制作日期：2026-08-05

## 前言：问题范围

R68 审计了柯力 v5（listed_company）的 18 个 `_build_*` 模块，发现 6 个完全静默失败（日志级别 `logger.debug` 吞掉异常）。用户追问：**行业深度（industry_deep）和非上市公司（unlisted_company）这两类报告，是否也存在类似的框架定义存在但执行丢失的问题？**

答案是：**存在，且比 listed_company 更严重**。listed_company 的问题主要是"数据链断了"（6 个模块需要 market_cap/fcf/capex 等字段，enrich 不提供）。行业和非上市的问题更底层——**部分 SAC 维度根本没有对应的注入模块，另一部分有模块但从未被设计接线**。

---

## 一、行业深度（industry_deep）—— 5 项框架丢失 / 接线断裂

### 1.1 已执行的 7 个

| 模块 | SAC 维度对应 | 柯力 v5 表现 |
|------|------------|-----------|
| ac_str（反共识） | core_disagreement | 通用计算，数据无关，正常 |
| bn_str（瓶颈分析） | industry_chain + profit_pool | 行业数据完备，正常 |
| cat_str（催化剂日历） | capital_market sub_question | 从 enrich 文本提取 |
| surp_str（预期差） | capital_market sub_question | 行业财务数据可访问 |
| pm_str（对标矩阵） | peer_benchmarking | peer_valuation.json 有数据 |
| bm_str（基准对标） | 资本市场映射 | 沙箱约束 |
| vc_str（估值交叉） | 估值映射 | 行业估值数据不完整 |

### 1.2 丢失或断裂的 5 个

**缺口 1：mr_str（分析方法论规则）— 对行业报告完全静默**

SAC 行业深度第 2 步弹性分析维度要求：需求收入弹性、需求价格弹性、供给价格弹性、交叉价格弹性 + 弹性矩阵（王思宇框架）。对应的 knowledge 注入函数 `_build_methodology_injection()` 需要 `topic_map` 映射。`topic_map` 对 `listed_company` 只映射 `business_model` 主题，对 `industry_deep` 映射什么主题没有配置。结果：行业报告的任意一个 segment 都没有方法论框架注入——写了"弹性分析"但分析结构是空的。

**缺口 2：ts_str（三表勾稽）— 行业报告根本不需要但 prompt 仍注入，浪费 token**

`ts_str` 无条件对所有报告类型执行 `_serialize_data` → `format_three_statement`——有 margin/capex/wc 字段就有产出，没有就静默跳过。行业报告的 `data_context` 中通常只有宏观数据、股价、估值，没有公司的 margin/wc。结果：行业报告的 prompt 中 `ts_str` 永远为空，但不影响生成——浪费了 token 和逻辑。

**缺口 3：fc_str（盈利预测）— 行业报告不适用，但没有对应的"行业盈利预测"替代模块**

`fc_str` 是为个股估值设计的（三表联动、销量/价格分解）。行业报告需要"行业盈利预测"——行业的整体盈利、毛利、ROE 趋势、需求端/成本端双变量敏感性。行业 SAC 中有 `capital_market` 维度定义了"行业定价、一致预期差、戴维斯双击/双杀"，却没有任何 `_build_*` 模块把行业的戴维斯双击逻辑注入 prompt。LLM 需要自己在 26 个 sub_question 中找到该问的来回答——这取决于 LLM 的偶然性，不是结构化的注入。

**缺口 4：ma_valuation（并购估值/行业整合）— 定义在框架注册表但从未真正接线**

framework_registry 中 `ma_valuation` 的 "注入方式" 写的是 `core.compute.consolidation → compute`。追查代码：`core.compute.consolidation.py` 放在 `core/compute/` 下，但在 `pipeline/compute_engine.py` 中**没有调用点**。section_writer 中没有 `_build_ma_injection()` 函数。SAC 行业深度有 `industry_consolidation` 维度定义了"行业是否在整合、谁是整合者/被整合者、并购估值倍数、ROIC vs WACC、判断行业终局"。定义在、注册在、但没有代码消费。这是一个**框架注册但完全接线为零**的设计空洞。

**缺口 5：elasticity_analysis（弹性分析）— 在 compute 中有工具但行业报告 prompt 中注入缺失**

弹性分析在 compute_engine 中作为 tool_modules 正常产出。但在 section_writer 的 `_build_tool_modules_injection()` 中，弹性分析只注入到 listed_company 的 seg2（前瞻层）。行业报告的三段分割不同：seg0(战略) → seg1(竞争) → seg2(前瞻)。弹性分析属于 seg2 但 `seg_tools` 映射是写死的 `{2: ["elasticity", "multi_model"]}`。只要行业报告的三段编号有偏移，弹性分析就不会被注入。

---

## 二、非上市公司（unlisted_company）— 4 项框架丢失 / 接线断裂

### 2.1 已执行的专属模块

| 模块 | SAC 维度对应 | 状态 |
|------|------------|------|
| ur_str（非上市反向定价） | valuation_estimate + exit_analysis | 有代码，只对 unlisted 类型触发 |

但 ur_str 的触发条件是 `if self.report_type == "unlisted_company"`。它依赖 `build_unlisted_reverse_valuation(data_context)`，而该函数从 `chart_data` 中提取估值数据（营收、PS 倍数、可比估值）。如果 enrich 没有结构化这些字段，ur_str 会静默失败——与 listed_company 的反向 DCF 同根因。

### 2.2 丢失或断裂的 4 个

**缺口 6：非上市稀有性 / 威胁度判断 — SAC 定义了但没有注入模块**

SAC 非上市维度有 `unlisted_threat`（非上市威胁判断），要求"非上市关键玩家名单 + 市场地位 + 威胁度判断（高/中/低）+ 战略动作分析"。这个维度的逻辑由 `unlisted_players.json` 和 `UniverseBuilding` 节点负责数据，但没有一个 `_build_unlisted_threat_injection()` 函数把非上市玩家的威胁度量化（高/中/低）注入到写作 prompt。LLM 能看到 `unlisted_players.json` 的玩家名单，但看不到系统对威胁度的结构化判断。

**缺口 7：退出路径分析 — SAC 有，但没有对应的注入模块**

SAC 非上市维度有 `exit_analysis`（退出路径：IPO/并购/下一轮融资判断）。section_writer 里没有对应的 `_build_exit_analysis_injection()` 函数。LLM 需要自创退出判断，没有来自系统的结构化信号（可比退出案例、退出倍数、退出门槛）。

**缺口 8：商业模式验证 — SAC 定义了但数据处理空转**

SAC 非上市维度有 `business_model`（产品/技术/团队/客户）。enrich 有 `company_intro` 文本可以注入，但 `hf_str`（哈佛框架）依赖 `data_context` 中结构化的 `biz_model` 对象——而非上市公司的 enrich 只有非结构化文本。所以哈佛框架对 unlisted 完全静默。

**缺口 9：SAC 覆盖的非上市量化信号 — UniverseBuilding 已算出来但没注入 prompt**

UniverseBuilding 节点产出 `universe_summary`（coverage_rate、missing_players、brand_issues、group_notes）。这个摘要被注入到了 perform_enrich 和 IronGate 的 coverage_check 中——但**没被注入到 section_writer 的 prompt** 中。LLM 在写作时不知道该报告存在"品牌映射缺失"或"集团归属被修正"的问题。

---

## 三、对比：三类报告，谁的框架损失最严重

| 维度 | listed_company | industry_deep | unlisted_company |
|------|--------------|-------------|----------------|
| 18 模块静默失败 | 6 个（33%） | 5 个（28%，但另有 2 个对行业无意义却注入） | 4 个（22%，但另有 2 个设计空洞） |
| 注册但未接线的框架 | 无 | 1 个（ma_valuation） | 无 |
| SAC 维度无注入模块 | 无（全部 7 个 sub_question 在 prompt 中） | 3 个：戴维斯双击、弹性矩阵、行业盈利预测 | 2 个：非上市威胁度量化、退出路径 |
| 计算产出但未注入 prompt | 2 个：反向 DCF + 多空表 | 1 个：universe_summary | 2 个：universe_summary + 非上市威胁 |
| **框架损失总数** | **8 个** | **9 个** | **8 个** |

---

## 四、根本原因的统一诊断

三类报告的框架损失有共性的三层次：

**层次 1：注入路径的物理分割**

15 个注入模块被放在 section_writer 最末端（1500-1710 行），与 5 核心工具（compute → tool_modules → prompt）是两个不同的世界。核心工具有 ok/skip/error 三态，注入模块有"有/无"二态。核心工具失败产生 "skip" 信号，注入模块失败产生空字符串——对下游完全透明。

**层次 2：SAC 维度与注入函数没有双向映射**

没有一份文件列出 "SAC 维度 X → 由模块 Y 注入"。当前的映射是单向的：模块函数迭代 SAC 维度 ID 列表选择一个子集，但没有从 SAC 维度出发的"我应该被谁注入"的反向检查。这种单向映射让框架注册了但接线缺失无法在事前检测。

**层次 3：ma_valuation 是这三种根因的最典型案例**

SAC 有维度、registry 有注册、compute 有代码——唯独缺少 "谁来调用它" 的接线。这和其他模块的 "有注入但数据断链" 不同，ma_valuation 是整个框架生命周期的第一步（注册）到第四步（执行）都衔接上了，就是到接线这一步卡住了。

---

## 五、修复优先级

| 优先级 | 缺口 | 动作 |
|--------|------|------|
| **P0** | ma_valuation 完全未接线 | 在 section_writer 加 `_build_ma_injection()`，消费 `core.compute.consolidation` 产出 |
| **P0** | 行业弹性矩阵注入偏移 | 修复 `seg_tools` 映射，支持行业报告的三段结构 |
| **P0** | unlisted_company 非上市威胁度 | 加 `_build_unlisted_threat_injection()`，从 UniverseBuilding 的 universe_summary 注入 |
| **P1** | 方法论规则对行业报告的映射 | 扩展 topic_map 到 industry_deep 的全体维度 |
| **P1** | 行业报告无"戴维斯双击"模块 | 加 `_build_industry_davis_doubleplay_injection()`，从 consensus_prices + macro 计算 |
| **P2** | 退出路径分析 | 加 `_build_exit_analysis_injection()`，从 unlisted_players + m_and_a_cases 注入 |
| **P2** | UniverseBuilding 的摘要不注入 prompt | section_writer 加 `_build_universe_summary_injection()` |

---

**一句话总结**：行业和非上市报告框架缺失的根因比 listed_company 更深——不是数据链断了，而是 SAC 定义了、registry 注册了、compute 算出来了，但**接线这一步从未被设计**。
