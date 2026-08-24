---
用途: 报告质量评分标准
版本: 1.0
使用场景: 评分引擎 ScoreEngine 的评分维度定义
来源: SKILL.md §二-Step5 / core/quality_scorer.py / pipeline/agent_loop.py
---

## ScoreEngine 8维评分体系

| 维度 | 权重 | 说明 | 检测方式 |
|------|------|------|---------|
| AIGC指纹 | 15% | AI痕迹越少越好 | AIScanner |
| 人感 | 10% | 资深分析师语气 | HumanSenseDetector |
| 质量 | 20% | 论证深度+数据质量+可读性 | QualityScorer |
| SAC覆盖 | 15% | SAC维度覆盖度 | 正则统计 |
| 图表密度 | 15% | 图表数量和分布 | 正则统计 |
| 数据可追溯 | 10% | 有来源标注 | 正则检查 |
| 排版一致性 | 5% | 无排版问题 | FormatProfessionalizer |
| 说服力架构 | 10% | 有叙事弧线 | 关键词检测 |

**综合评分 >= 0.9 才能进入 Iron Gate。**

## QualityScorer 10维深度评分

| 维度 | 权重 | 说明 |
|------|------|------|
| narrative_grip | 10% | 叙事吸引力 — 关键词：关键、出乎意料、拐点、分歧 |
| surprise_premium | 15% | 意外溢价 — 但与市场共识不同超出预期 |
| concreteness | 15% | 具体性 — 避免"很多大量显著"等模糊词 |
| depth_chain | 10% | 因果链 — 因为所以因此这意味着导致 |
| structure | 10% | 结构完整度 — 章节完整、逻辑递进 |
| evidence_density | 15% | 证据密度 — 据来源数据显示表明 |
| actionability | 10% | 可操作性 — 建议推荐买入卖出 |
| precision | 5% | 精确度 — 具体数字%±区间 |
| source_credibility | 5% | 来源可信度分级 — 硬数据vs测算区分 |
| experience_citation | 5% | 经验引用 — 从业多年历史规律行业规律 |

**综合评分 >= 0.90 且所有单维度 >= 0.50 才算通过。**

## DeepSeek辅助评分维度（启用时参考）

1. aigc_fingerprint (0-1): AI痕迹分数，越低越好（人类写作应<0.15）
2. human_sense (0-1): 人感分数，越高越好
3. argument_depth (0-1): 论证深度
4. data_quality (0-1): 数据质量
5. chart_density (0-1): 图表密度
6. persuasion (0-1): 说服力
7. formatting (0-1): 排版质量

### 评分等级
- 9-10: 中金/高盛/McKinsey级别顶级报告
- 7-8: 一级券商优质报告
- 5-6: 合格的分析报告
- 3-4: 有明显缺陷
- 0-2: 不合格
