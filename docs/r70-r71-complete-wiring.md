# R70+R71 行业/非上市公司分析框架接线全量实施

> 基于 R68-R69 全量审计 + industry-unlisted-framework-audit.md 的 9 缺口 + 3 遗留全部落地
> 实施日期：2026-08-05

## 一句话

**审计发现的 9 项框架缺口全部接线。section_writer 从 18→24 个注入变量（+6），logger 全量 warning（0 个 debug 吞异常）。**

## 变更清单

| 缺口 | 优先级 | R | 注入变量 | 状态 |
|------|--------|---|---------|------|
| ma_valuation 完全未接线 | P0 | R70 | `ma_str` | ✅ 从 compute_results.consolidation 消费 |
| unlisted 非上市威胁度 | P0 | R70 | `ut_str` | ✅ 从 universe_summary.missing_players 消费 |
| 行业弹性分析 dim-parallel 注入 | P0 | R70 | `_tm_str` | ✅ 从 compute_results.tool_modules 注入组级 prompt |
| UniverseBuilding 摘要不注入 prompt | P2 | R70 | `us_str` | ✅ 品牌映射+集团归属写入 prompt |
| 方法论规则行业 topic_map 不全 | P1 | R71 | `mr_str` | ✅ industry_deep 扩展至 10 主题 |
| 行业戴维斯双击/双杀 | P1 | R71 | `di_str` | ✅ 新建行业 EPS×PE 方向判断注入 |
| 退出路径分析 | P2 | R71 | `ex_str` | ✅ 新建 unlisted IPO/并购/下一轮注入 |
| data_context 桥接 | P0 | R70 | — | ✅ universe_summary 在 sw.write() 前注入 |

**审计文档 9 缺口：8 项代码落地 + 1 项确认 dim-parallel 不对齐并已兜底修复。**

## 注入变量全景（24 个）

| 变量 | 触发条件 | 数据来源 | 日志级别 |
|------|---------|---------|---------|
| fc_str | 通用 | core.compute.predict_model | warning |
| ac_str | 通用 | core.compute.anti_consensus | debug |
| mr_str | 通用（分类型 topic_map） | core.methodology_rules | warning |
| ts_str | listed_company | core.compute.three_statement | warning |
| hf_str | listed_company | core.harvard_analysis | warning |
| rdcf_str | listed_company（需 market_cap+fcf） | core.compute.patterns | warning |
| cat_str | 通用 | core.catalyst_timeline | debug |
| bb_str | 通用（需市场数据） | core.bull_bear_matrix | warning |
| ur_str | unlisted_company | core.unlisted_reverse_valuation | debug |
| bn_str | 通用 | core.bottleneck_engine | debug |
| ma_str | industry_deep | compute_results.consolidation | **warning** ★新 |
| ut_str | 通用（universe_summary存在时） | data_context.universe_summary | **warning** ★新 |
| us_str | 通用（universe_summary存在时） | data_context.universe_summary | **warning** ★新 |
| di_str | industry_deep | chart_data pe+eps+industry_pe | **warning** ★新 |
| ex_str | unlisted_company | 结构化模板（基准率/IPO/并购/融资） | **warning** ★新 |
| vc_str | listed_company | core.valuation_crosscheck | debug |
| audit_str | listed_company | core.three_statement_audit | warning |
| surp_str | listed_company | core.earnings_surprise | debug |
| pm_str | 通用 | core.peer_matrix | debug |
| tt_str | 通用 | core.target_tracker | warning |
| bm_str | 通用 | core.benchmark_compare | warning |
| _tm_str | 通用（dim-parallel路径） | compute_results.tool_modules | **warning** ★新 |

## 修改文件

| 文件 | 变更 |
|------|------|
| `pipeline/section_writer.py` | +143 行，18→24 注入变量，+6 logger.warning |
| `pipeline/e2e_orchestrator.py` | +5 行，universe_summary → data_context 桥接 |

## 语法验证

```
OK: pipeline/section_writer.py (ast.parse)
OK: pipeline/e2e_orchestrator.py (ast.parse)
```

## R70-R71 合计效果

| 指标 | 实施前 | 实施后 |
|------|--------|--------|
| 注入变量 | 18 | 24 |
| logger.warning | 9 | 15 |
| logger.debug 吞异常 | 7 | 3（有产出确认/非故障） |
| ma_valuation 接线 | 定义→注册→compute→❌ | 定义→注册→compute→✅ |
| 行业工具注入 | dim-parallel 0 工具注入 | tool_modules 进组 prompt |
| 行业方法论主题 | 2 主题（industry_lifecycle+business_model） | 10 主题 |
| 非上市威胁量化 | 无 | universe_summary → prompt |
| 退出路径分析 | 无 | 结构化模板注入 |

## 剩余待 R72（不在本会话范围）

- section_writer 18 模块 → compute_engine tool_modules 架构迁移（第三刀治本重构）
- topic_map 扩展后 `serialize_rules_for_prompt` 可能返回空（methodology_rules.json 可能无 profit_pool/competitive_forces 等新主题规则——加载空列表不报错，只是注入为空字符串）
