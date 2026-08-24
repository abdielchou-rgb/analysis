# prompts/INDEX.md

> 版本: 1.0 | 2026-07-27
> 用途: prompts 目录索引，Agent在写作前必须加载对应的prompt文件

---

## system/ — 角色设定

| 文件 | 用途 |
|------|------|
| cicc_analyst.md | 中金风格资深分析师 System Prompt（周力，15年经验） |
| goldman_sachs.md | 高盛风格投资银行分析师 System Prompt |
| mckinsey_consultant.md | 麦肯锡风格战略顾问 System Prompt |
| common_principles.md | 所有风格共享的核心原则（FP4/数据零编造/排版规范） |

**使用规则**: Agent在写作前加载对应风格的 System Prompt + common_principles.md。common_principles.md 是所有风格的基础层，必须先加载。

---

## writing/ — 写作prompt

| 文件 | 用途 |
|------|------|
| industry_deep.md | 行业深度研究报告 User Prompt 模板（含图表嵌入/推理链/So What约束） |
| listed_company.md | 上市公司分析 User Prompt 模板 |
| unlisted_company.md | 非上市公司分析 User Prompt 模板 |

### writing/sections/ — 各章节写作prompt

| 文件 | 用途 |
|------|------|
| executive_summary.md | 三段式写作引擎的每段独立调用约定 |
| business_analysis.md | 业务分析/商业模式章节写作指南 |
| financial_analysis.md | 财务分析/估值章节写作指南 |

**使用规则**: writing/ 下的模板需要注入实际数据（data_context、chart_metadata、report_sections）后使用。写具体报告时，使用对应的报告类型模板 + 数据填充。

---

## quality/ — 质量评分

| 文件 | 用途 |
|------|------|
| scoring_criteria.md | ScoreEngine 8维评分体系 + QualityScorer 10维深度评分标准 |
| calibration_hints.md | 评分校准规则、偏差纠正、Iron Gate校验项、图表/字数门禁 |

**使用规则**: 评分时参考 scoring_criteria.md 的维度和权重定义。校准参考 calibration_hints.md 的规则。

---

## 加载顺序

`
1. prompts/system/common_principles.md          # 基础原则（必须）
2. prompts/system/{style}_analyst.md             # 机构风格（按需）
3. prompts/writing/{report_type}.md              # 报告模板（按需）
4. prompts/quality/scoring_criteria.md           # 评分标准（评分时）
`

---

## 维护备注

- 所有prompt文件保持 frontmatter 格式（--- 分隔的元数据）
- prompt源文件不应暴露内部方法论标签（SAC、FP4、Iron Gate等）
- 新增报告类型 → 在 writing/ 下添加对应模板
- 新增机构风格 → 在 system/ 下添加对应角色设定
