# R81 框架利用全量优化——执行记录

> 修复"框架存在但没用上"：注入只取前4、无应用结论强制、指令无映射表
> 日期：2026-08-06

## 已落地（4 项）

1. **框架注入扩容+优先**（core/framework_injector.py）
   - 注入数量从 top4 扩到 top6
   - 关键框架优先排序（moat/competition/value_driver/strategy_engine/cycle/expectations/signal_noise/accounting）

2. **框架应用结论强制**（core/framework_injector.py）
   - prompt 尾部加"每个框架必须给出具体应用结论，禁止只提框架名"

3. **执行指令补框架→章节映射表**（r81-marvis-execute-oil-report.md）
   - 10 章映射：竞争真相→competition_demystified、供应链→bottleneck_engine、政策→signal_chain+signal_noise、技术栈→moat、生产主体→strategy_engine、收购定价→ma_valuation、财务→value_driver、目标价→expectations、敏感性→scenario、商誉→accounting

4. **补 3 个 SAC 维度章节**
   - 1.5 非上市威胁（unlisted_players）
   - 1.6 行业整合趋势（industry_consolidation）
   - 2.4 全球对标（global_competition）

## 关键修正
- `_KEY_FRAMEWORKS` 原含 bottleneck_engine/ma_valuation/scenario_analysis，但它们走 analyst_planner 另一套（data/framework_registry.json），不在 core/frameworks YAML → 已修正为 YAML 实际存在的 id

## 回归
49 pytest 全绿

## 效果
- 框架注入 6 个（关键框架优先）+ 强制应用结论
- 执行指令明确每章用什么框架
- 油位报告将体现"用瓶颈引擎拆解的磁致伸缩丝卡脖子""用并购估值算的华虹定价"
