# R68 偏离框架追溯 — 18 个模块静默失败审计

> 制作日期：2026-08-05 ｜ 基于自查：section_writer 中全部 `_build_*` 函数在柯力 v5 的实际执行结果

## 一句话结论

**18 个分析注入模块中，8 个完全成功、2 个部分成功、6 个完全静默失败、2 个因设计/环境约束失败。静默失败率 33%。**
全部 18 个模块使用同样的异常屏蔽模式（`except → logger.debug → 空字符串`），导致失败不可观测。

## 15 个注入模块全量清单（柯力 v5 DOCX 实测）

| 模块 | 关键词搜索 | DOCX命中 | 数据需求 | 失败原因 |
|------|-----------|---------|---------|---------|
| ac_str 反共识信号 | 反共识/分歧 | ✅ 8处 | data_context | — |
| cat_str 催化剂日历 | 催化剂/季度 | ✅ 11处 | enrich text | — |
| bn_str 瓶颈分析 | 瓶颈/卡点 | ✅ 6处 | industry_chain | — |
| vc_str 估值交叉 | 交叉验证 | ✅ 1处 | compute_results | — |
| surp_str 预期差 | 预期差 | ✅ 6处 | EPS consensus | — |
| pm_str 对标矩阵 | 对标/可比 | ✅ 7处 | peer_valuation | — |
| bm_str 基准对标 | 基准/vs指数 | ✅ 1处 | 行情数据 | — |
| **fc_str 盈利预测** | 盈利预测 | ❌ **0处** | 量/价结构化 | data_dict有 revenue 但无量价分解 |
| **ts_str 三表勾稽** | 三表/勾稽 | ❌ **0处** | capex/wc | data_dict 无 capex/wc 字段 |
| **hf_str 哈佛框架** | 哈佛/四步 | ❌ **0处** | biz_model 结构体 | data_context 缺 biz_model |
| **mr_str 方法论规则** | 方法论/投行框架 | ❌ **0处** | topic_map | listed_company 的 valuation 主题未映射 |
| **audit_str 审计核查** | 审计式 | ❌ **0处** | financials.db | balance表覆盖率3% |
| **tt_str 目标价追踪** | 目标价追踪 | ❌ **0处** | forward_picks | 12条全pending(2027到期) |
| rdcf_str 反向DCF | 反向DCF/隐含增速 | ✅ 1处 | market_cap+fcf | 失败→但报告可能自己写了"反向DCF"字样 |
| bb_str 多空表 | 多空 | ⚠️ 2处 | 市场数据 | 结构不完整 |

## 失败类型分布

**P0 数据依赖（4 个）**：rdcf_str, bb_str, fc_str, ts_str——需要市场数据或财务明细，柯力 enrich 不提供
**P0 知识库依赖（1 个）**：mr_str——方法论主题映射不完整
**P1 数据依赖（2 个）**：hf_str, audit_str——需要结构化的业务模型或高覆盖率财务数据库
**P2 设计约束（2 个）**：tt_str, bm_str——需要已验证的预测数据或真实行情（沙箱不可得）

## 为什么全静默

全部 16 个异常日志使用 `logger.debug`——这是 Python logging 的**最低级别**，默认关闭，生产环境看不到：

```
1462: logger.debug("[PREDICT] %s", _e)     → fc_str 失败
1482: logger.debug("[RULES] %s", _e)       → mr_str 失败
1492: logger.debug("[THREE-STMT] %s", _e)  → ts_str 失败
1499: logger.debug("[HARVARD] %s", _e)     → hf_str 失败
1516: logger.debug("[REVERSE-DCF] %s", _e)→ rdcf_str 失败
1534: logger.debug("[BULLBEAR] %s", _e)   → bb_str 失败
```

## 根本原因

这 18 个模块被设计成 **section_writer 的末端装饰品**，不是 **compute_engine 的核心产出物**。它们的数据依赖关系和失败模式在架构层面不可见——因为不在 compute 的 tool_modules 路径中，section_writer 把它们当作可选的 prompt 增强，静默失败是可接受的行为（异常被 mask 掉）。相比之下，life_cycle / signal_chain / elasticity / multi_model / moat（5工具）在 compute 中产出结构化结果——如果失败会返回 "skip" 状态，在 prompt 中也显式标注 "skip"——这个设计差距导致了整整三层分析能力的静默丢失。
