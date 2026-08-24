# R77 Marvis 久通物联自检报告验证

> 验证 Marvis 声称的 R1-R13 修复落地真实性 + 副作用排查
> 日期：2026-08-05

## 结论

Marvis 自检报告 **R1-R13 修复大部分真实落地**，但存在 **1 个破坏性 bug + 2 个误伤 bug**，均已修复。

## 已验证落地（✅）

| 修复 | 验证结果 |
|------|----------|
| R1/R3 _inject_report_header | ✅ 实现存在（datetime 注入系统日期+署名） |
| R2 _check_report_date | ✅ 注册进 Gate；正确日期通过、无日期阻断 |
| R4 _check_placeholder_xxx | ✅ 注册进 Gate；真实占位符拦截 |
| R5 data_caliber infer_caliber_with_source | ✅ 实现存在 |
| R6 _check_cross_section_consistency | ✅ 注册进 Gate |
| R7 端侧硬编码句删除 | ✅ style.py 无"端侧产品放量" |
| R8/R9 So What 去重/表格跳过 | ✅ text.count>=2 存在 |
| R10/R11/R12 chart_failures 标记 | ✅ chart_pipeline 记录失败原因 |
| R13 PE_VC 豁免 | ✅ PE_VC_DIM_IDS 存在 |

## 发现并修复的 bug

### Bug1（破坏性）：AgentEnricher.merge 复合结构破坏下游
- Marvis 把 fig_data 改为 `{"data":..,"unit":..,"note":..}` 复合结构
- **破坏**：chart_gen/compute_engine/section_writer 直接按扁平 dict 读 fig_*，静默丢数据
  （实测增速返回 []、图表空）
- **破坏**：test_data_enrichment.py 断言 `cd["fig_revenue_trend"]["2024"]==60` KeyError
- **修复**：merge 保持扁平 chart_data + 伴生 `_caliber` 字典存 unit/note/source

### Bug2（误伤）：占位符检查拦截中文省略号
- `(r'…{2,}', "省略号占位")` 把正常中文省略号"……"误判为占位符
- **修复**：删除省略号规则

### Bug3（漏检）：\b 边界在中文上下文失效
- `\bXXX\b` 在中文文本不匹配（\b 只认 ASCII word boundary），"我们判断XXX"漏检
- **修复**：去掉 \b，直接匹配 XXX/TODO/TBD/FIXME

## 新增回归测试

- `tests/test_r77_marvis_validation.py`（7 项）：日期检查/占位符/扁平 merge/端侧硬编码/跨节一致性

## 回归

- 51 pytest + 25 data_enrichment + 7 marvis_validation 全绿
- 关键批次：test_fact_quality(23)/test_e2e_keli(5)/test_r61(7)/test_r77×4
