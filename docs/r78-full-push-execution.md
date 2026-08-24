# R78 全量推进执行记录

> 基于 full-audit-and-engineering-plan-20260805.md Phase 1/2/4 全量推进
> 日期：2026-08-05

## 已完成

### Phase 1.3 SAC sub_elements 全维度
- industry_deep 4/26 → 14/26 维有高质量 sub_elements（手写同义词正则）
- 新增维度裁剪豁免：报告未涉及维度（核心词不出现）→ 豁免子要素
- 真实报告覆盖 69%→77% 通过，正确暴露软覆盖
- 教训：自动派生正则质量差，必须手写同义词括号正则

### Phase 1.4 calibrated_thresholds 默认档
- 新建 benchmark/calibrated_thresholds.json（11 项阈值基线）
- 此前缺失导致 Gate 降级到硬编码默认

### Phase 2.2 learning DB 迁移
- output/learning_data.db → data/learning_data.db（防 cleanup 误删）

### Phase 2.4 短周期预测 + forward_picks 修复
- 新建 core/short_term_signals.py：资金面（北向/龙虎榜）→ 3M 可验证信号 → 独立台账 data/short_term_signals.csv
- **修复 forward_picks 静默失败**：e2e 里 `fdb.record_prediction` 不存在（ForwardPicksDB 重构后只剩 append），AttributeError 被 try 吞（预测从未入库）。改用 ForwardPick + append

### Phase 2.5 chaos 常态化
- chaos_test.py 验证 3/3 通过（provider 降级/数据源/管线韧性）

### Phase 4.4 industry_dimension_weights
- 新建 data/industry_dimension_weights.json（10 行业×维度权重）
- analyst_planner 消费：industry_deep 下按权重排序 focus（technology 权重9 排最前）
- core_dims 从中文名改为 SAC 英文 ID（消除命名混乱）
- 权重表键=industry_deep 体系，仅该类型生效（诚实降级其他类型）

### Phase 4.5 美股/港股链路核查
- load_us_stock/load_global_leaders/load_us_highfreq 已存在

## 未完成（Phase 1 数据契约/golden dataset）

- 1.1 数据契约 JSON Schema：工作量大，需定义 chart_data/enrich_file/financials schema
- 1.5 golden dataset + LLM judge：需收集 10-20 条黄金样本
- 2.1 OpenTelemetry 全链路 trace：依赖外部服务
- 2.3 写改循环 SQLite checkpoint：架构级改动
- 3.x 拆分上帝模块：1-2 周工作

## 回归

- 41 pytest 全绿（含新增 sub_elements/planner 相关测试）

## 关键 bug 修复汇总

1. **forward_picks 静默失败**（e2e record_prediction 不存在）
2. **SAC 维度裁剪豁免**（自动派生正则打爆真实报告）
3. **planner core_dims 中文名不匹配 SAC 英文 ID**
4. **industry weights 只对 industry_deep 生效**（其他类型诚实降级）
