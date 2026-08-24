"""
V53 Persuasion Architecture — 说服力架构

在 LLM prompt 中注入叙事弧约束, 让报告从"数据堆砌"变成"有说服力的叙事"。

Onion Architecture:
  外层: 叙事弧 (Hook -> Context -> Analysis -> Counter-argument -> Conclusion -> CTA)
  中层: SAC 维度 (行业/公司/估值各维度)
  内层: 数据证据链 (每个判断都有数据支撑)
"""

from core.models import KnowledgePackage
from typing import Optional

# ──────────────────────────────────────────────
# 叙事弧模板
# ──────────────────────────────────────────────

NARRATIVE_ARC = """
## 叙事弧线约束

整份报告必须遵循以下叙事结构, 不可打乱顺序:

1. **Hook**（1段）: 第一段必须是一个让人想继续读下去的开头。
   - 好的 Hook: "市场普遍认为XX行业已经见顶, 但我们的分析得出了相反的结论。"
   - 差的 Hook: "本文对XX公司进行了深度分析。" (太无聊)

2. **Context**（1-2段）: 解释为什么现在是讨论这个主题的时机。
   - 宏观背景变化、行业拐点信号、市场定价偏差等。

3. **Analysis**（核心正文）: 按 SAC 维度展开论证。
   - 每个大论点必须有: 数据支撑 -> So What 分析 -> Now What 建议。

4. **Counter-argument**（1-2段）: 主动提出最强的反对论点, 然后反驳。
   - "反对者认为...但我们的观点是..."

5. **Conclusion**（1段）: 总结核心判断, 重申 Conviction。

6. **Call to Action**（1段）: 给出具体的投资建议或下一步行动。
   - "基于以上分析, 我们建议..."
"""

COUNTER_ARGUMENT_TEMPLATE = """
## 反方论点处理

在报告主体中, 至少有一个专门的段落处理与你们结论相反的论点:

1. 明确写出最强的反对论点（引述市场共识或怀疑者观点）
2. 用数据和逻辑逐一反驳
3. 如果某些反对论点无法反驳, 诚实地承认并标注不确定性

示例:
"市场担忧的三个方面: (1)...(2)...(3)... 我们认为:
- 针对(1): 虽然...但历史数据显示...
- 针对(2): 数据表明...
- 针对(3): 这一担忧合理, 但影响有限..."
"""

CALL_TO_ACTION_TEMPLATE = """
## 行动号召要求

报告的最后一节（附录之前）必须是明确的行动号召:

1. **投资建议**: 买入/持有/卖出 + 目标价 + 时间框架
2. **催化剂**: 接下来6-12个月的关键催化剂事件
3. **风险监控**: 需要关注的关键指标和阈值

不接受的结尾:
- "以上分析仅供参���" (太弱)
- "需持续关注" (等于没说)
"""


def build_persuasion_prompt(kp: KnowledgePackage) -> str:
    """根据报告类型生成说服力约束"""
    report_type = kp.brief.report_type.value if kp.brief and kp.brief.report_type else "listed_company"
    
    blocks = [NARRATIVE_ARC, COUNTER_ARGUMENT_TEMPLATE, CALL_TO_ACTION_TEMPLATE]
    return "\n\n".join(blocks)
