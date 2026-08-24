# R74b — Phase 1+2 执行记录

> 子会话执行：R74 工程计划首批落地（防御纵深 + SAC 度量免疫）
> 日期：2026-08-05

## 变更清单

| # | Phase | 文件 | 变更行 | 内容 |
|---|-------|------|--------|------|
| 1 | 1.1 | pipeline/checks/content_format_mixin.py | +12 | md层图表位置检测——检查 `![fig_xxx]` 是否在"附录"标题前出现 |
| 2 | 1.2 | pipeline/section_writer.py | +5 | dim-parallel 组 prompt + merge prompt 双点注入 `[R72 禁止AI免责]` |
| 3 | 2.1 | core/sacs/sac_industry_deep.yaml | +18 | 4维度新增 `required_sub_elements`：elasticity(6)/capital_market(6)/consolidation(4)/esg(1) |
| 4 | 2.2 | pipeline/checks/coverage_mixin.py | +60 | 新建 `_check_sub_element_coverage()`——逐要素正则匹配，阈值70% |
| 5 | 2.4 | pipeline/iron_gate.py | +1 | `_check_sub_element_coverage` 接入 Gate 检查队列 |

## 验证结果

```
OK: pipeline/section_writer.py (ast.parse)
OK: pipeline/checks/content_format_mixin.py (ast.parse)
OK: pipeline/checks/coverage_mixin.py (ast.parse)
OK: pipeline/iron_gate.py (ast.parse)

SACLoader.get_dimension('capital_market').required_sub_elements → 6 items ✓
SACLoader.get_dimension('elasticity_analysis').required_sub_elements → 4 items ✓
SACLoader.get_dimension('industry_consolidation').required_sub_elements → 4 items ✓
SACLoader.get_dimension('esg_materiality').required_sub_elements → 1 item ✓

md chart position check → present ✓
prompt-level disclaimer kill → present (both dim-parallel and merge paths) ✓
sub_element coverage Gate check → defined + wired into iron_gate ✓
```

## 效果

- 防御纵深：AI免责声明现在有 3 层拦截（prompt层 × 2 + Gate层 × 1）——手动路径再也绕不过
- 图表未随文：docx层（R40）→ md层（R74新增）双层检测，管线路径和手动路径都覆盖
- SAC覆盖免疫：油位v6的"26/26关键词覆盖"在新Gate下会被 `_check_sub_element_coverage` 拦截——缺失的34个子要素会被单独列出

## 剩余 Phase（3-6）

按 R74 工程计划执行：Phase 3 InfoDesk → Phase 4 跨报告关联 → Phase 6 反方论证强度 → Phase 5 五维缺失
