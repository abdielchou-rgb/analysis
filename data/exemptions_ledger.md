---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 078a03d61572168cce0dea376dc7babb_4f9bba8a920b11f1bafa525400287e28
    ReservedCode1: XtrP807KDI96KnTYN60Fh4SZVOnGpV5OBmhvuk2ngfbveHdTQu7SLErVs7uxvov3v+dYNhJVrKffmaivbSjCIw5TMFPuakIhYGVjertoAHTvekMif2+oUb2f03JZLesLRiwmo5RQwCbeUCq33M9kkB3Bo1jrpsNTAovPXylNRNSHfO/M7oKT7jrtuSo=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 078a03d61572168cce0dea376dc7babb_4f9bba8a920b11f1bafa525400287e28
    ReservedCode2: XtrP807KDI96KnTYN60Fh4SZVOnGpV5OBmhvuk2ngfbveHdTQu7SLErVs7uxvov3v+dYNhJVrKffmaivbSjCIw5TMFPuakIhYGVjertoAHTvekMif2+oUb2f03JZLesLRiwmo5RQwCbeUCq33M9kkB3Bo1jrpsNTAovPXylNRNSHfO/M7oKT7jrtuSo=
---

# 豁免台账（Exemptions Ledger）

**创建时间**：2026-08-07  
**关联轮次**：R84（油位传感器决策备忘录 v0.90）  
**回扫日期**：2026-11-07（季度回扫）  
**维护人**：Pipeline Administrator  

---

## 说明

本台账记录 `IronGate.run_all()` 中因业务场景特殊性或当前管线能力边界而给予豁免（waiver）的检查项。  
豁免分类：

| 类别 | 含义 | 处理方式 |
|------|------|---------|
| **A** | 结构性豁免：当前管线或数据层不支持此检查，非报告质量问题 | 季度回扫，管线更新后重新评估 |
| **B** | 上下文豁免：报告类型（decision_memo）天然不适用此检查 | 季度回扫，检查器适配后重新评估 |
| **D** | 数据层豁免：报告依赖的外部数据/模型不可用导致检查无法通过 | 季度回扫，数据就绪后重新评估 |

---

## R84 豁免清单（共 19 项）

| 序号 | 检查器名称 | 类别 | 豁免原因 | 得分 | 创建时间 | 回扫日期 |
|------|----------|------|---------|------|---------|---------|
| 1 | `financial_statements_coverage` | B | decision_memo 不要求完整三表分析，行业/市场数据为主 | 1.000 | 2026-08-07 | 2026-11-07 |
| 2 | `dcf_sensitivity` | B | decision_memo 为非上市公司决策备忘录，无 DCF 估值 | 1.000 | 2026-08-07 | 2026-11-07 |
| 3 | `rating_target_consistency` | B | decision_memo 无评级-目标价概念 | 1.000 | 2026-08-07 | 2026-11-07 |
| 4 | `financial_value_consistency` | D | 无 data_dict，无法校验财报数据一致性 | 1.000 | 2026-08-07 | 2026-11-07 |
| 5 | `data_dict_refs` | D | 数据字典层为空，无法校验引用完整性 | 1.000 | 2026-08-07 | 2026-11-07 |
| 6 | `data_fidelity` | D | 非上市公司无公开财报，数据保真度依赖委托方提供 | 1.000 | 2026-08-07 | 2026-11-07 |
| 7 | `stock_pick_chain` | B | decision_memo 非荐股报告，无选股链 | 1.000 | 2026-08-07 | 2026-11-07 |
| 8 | `valuation_integrity` | B | decision_memo 无估值章节 | 1.000 | 2026-08-07 | 2026-11-07 |
| 9 | `tam_bottomup` | B | decision_memo 市场规模引用行业报告自上而下数据 | 1.000 | 2026-08-07 | 2026-11-07 |
| 10 | `industry_consolidation` | B | decision_memo 聚焦单一赛道进入决策，非行业全景 | 1.000 | 2026-08-07 | 2026-11-07 |
| 11 | `regional_penetration` | B | decision_memo 为中国本土企业决策，不涉及跨区域渗透 | 1.000 | 2026-08-07 | 2026-11-07 |
| 12 | `esg_materiality` | B | decision_memo 客户未要求 ESG 实质性分析 | 1.000 | 2026-08-07 | 2026-11-07 |
| 13 | `geopolitical_depth` | B | decision_memo 国内制造业决策，地缘风险非核心维度 | 1.000 | 2026-08-07 | 2026-11-07 |
| 14 | `unlisted_threat` | B | decision_memo 本就是对非上市业务可行性分析 | 1.000 | 2026-08-07 | 2026-11-07 |
| 15 | `multi_model` | A | 管线多模型验证依赖 LLM 多 provider，当前仅单 provider 可用 | 0.667 | 2026-08-07 | 2026-11-07 |
| 16 | `ai_tone_by_llm` | A | LLM 判定器 DeepSeek API 不可用，降级为不确定性判定 | 0.500 | 2026-08-07 | 2026-11-07 |
| 17 | `human_impossible_dimension` | A | 部分维度（sources=2）依赖外部联网数据，管线当前受限 | 1.000 | 2026-08-07 | 2026-11-07 |
| 18 | `attribution_depth` | A | 因子分析/子因子层级未达满分，需人工标注增强 | 0.600 | 2026-08-07 | 2026-11-07 |
| 19 | `content_density` | D | DOCX 导出时图片内嵌可能导致密度计算偏低，MD 字数充足 | 0.700 | 2026-08-07 | 2026-11-07 |

---

## 后续行动

1. **季度回扫（2026-11-07）**：逐项复查，管线/数据更新后能通过则移出豁免。
2. **A 类项**：优先推动管线能力补齐（多 provider、联网数据增强）。
3. **B 类项**：推进 decision_memo SAC 适配，使检查器可判断报告类型自动跳过。
4. **D 类项**：数据字典建设完成后，重新评估 #4/#5/#6/#19。

---

## 变更记录

| 日期 | 变更内容 | 操作人 |
|------|---------|--------|
| 2026-08-07 | R84 初始创建，录入 19 项豁免 | Pipeline Administrator |
*（内容由AI生成，仅供参考）*
