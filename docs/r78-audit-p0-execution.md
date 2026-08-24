# R78 全量审计 P0 修复执行

> 基于 full-audit-and-engineering-plan-20260805.md Phase 0 P0 项
> 日期：2026-08-05

## 核验结论

审计报告 P0 声明**全部属实**，本次修复 P0-1/P0-2/P0-3 核心项。审计本身"未实跑 pytest"的 3 个 lastfailed 已实测为通过（旧缓存）。

## P0-1 出口门禁语义修复

| 问题 | 修复 |
|------|------|
| GateCheckResult severity 默认 warning，passed 只统计 error | 保持设计（warning 不阻断），但出口层补 hard_fail |
| export_report 只判 score 不判 passed | 增加 `ig_result.passed` 判定 → 阻断 |
| gates_config.yaml hard_fail 未消费 | export_report 消费 `hard_fail`/`require_all_hard` |
| score=1.673 未归一化 | iron_gate overall_score clamp [0,1]，单项 score 也 clamp |
| main.py Gate 失败仍写 MD + status=ok | Gate 未过 → status=error（MD 保留供审计） |

## P0-2 scheduler 死代码修复

| 问题 | 修复 |
|------|------|
| orchestrator.run() 返回 report_text 不返回 md | scheduler 从 report_text 写 MD → result["md"] |
| ChartEngine/二次IronGate/强制出口三段永不执行 | 写 MD 后三段正常执行 |
| 强制出口 export_report 未传 gate_result（双跑） | 透传 result["gate_report"] |
| export_report 只认对象形态 | 兼容 dict（to_dict() 结果）转换 |

## P0-3 安全与密钥管理

| 问题 | 修复 |
|------|------|
| .gitignore 全局 `*.md` 忽略文档 | 改为只忽略 output/产出 md |
| build-backend 非标准 | 修正为 `setuptools.build_meta` |
| 无 .env.example | 创建模板 |
| 无 git 仓库 | 待用户确认后 git init |
| key 泄漏 docs/ | 建议用户轮换 key（代码层无法清历史） |

## 回归

53 pytest 全绿（test_fact_quality/test_e2e_keli/test_r61/test_r77×4/test_r65/test_r55）。

## 剩余（未做）

- git init（需用户确认）
- Tavily key 轮换（用户操作）
- Phase 1-4（数据契约/golden dataset/OpenTelemetry/拆分上帝模块等）后续排期

---

## R78 Phase 1.3 + Phase 2 执行（2026-08-05 追加）

### Phase 1.3 SAC sub_elements
- industry_deep 从 4/26 维 → 14/26 维有高质量 sub_elements（手写同义词正则）
- 新增维度裁剪豁免：报告未涉及维度（核心词不出现）→ 豁免其子要素
- 真实报告子要素覆盖 69%→77% 通过，且正确暴露软覆盖（elasticity 写了维度但缺子要素）
- 新增 test_r77_marvis_validation 2 项测试

### Phase 2 可观测与演化闭环
- **learning DB 迁移**：output/learning_data.db → data/learning_data.db（防 cleanup 误删）
- **forward_picks 修复**：e2e 里 `fdb.record_prediction` 不存在（ForwardPicksDB 重构后只剩 append），旧调用 AttributeError 被吞（预测从未入库）。改为 ForwardPick + append
- **短周期信号模块**：core/short_term_signals.py——从资金面（北向/龙虎榜）生成 3M 可验证信号，写独立台账 data/short_term_signals.csv（不用 forward_picks 因 R64 强制 anchor_nav 会拒绝资金面信号）
- **chaos_test 验证**：3/3 通过（provider 降级/数据源韧性/管线韧性）

### 关键教训
- 自动派生 sub_elements 正则质量差（字面句式报告永不出现），必须手写同义词括号正则
- ForwardPicksDB 重构后 e2e 旧调用未同步——静默失败（try 吞 AttributeError）
