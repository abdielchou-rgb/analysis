"""
V53 Consensus Dialogue — 与市场共识的对话

在报告中生成"市场共识 vs 我们的判断"对比章节。
Consensus 数据从 consensus_connector 获取, 与 Conviction Matrix 交叉验证。
"""

from core.models import KnowledgePackage, DataPoint
from core.assumption_benchmark import AssumptionBenchmark
from typing import Optional

CONSENSUS_DIALOGUE_PROMPT = """
## "与市场共识的对话" 章节要求

在报告主体中包含一个专门的章节(至少1页), 回答以下三个问题:

### 1. 市场共识是什么？
- 目前市场对该公司/行业的普遍看法
- 分析师一致预期的营收/利润/目标价范围
- 市场定价隐含的假设

### 2. 我们在哪里与共识不同？
- 列出我们与市场共识的1-3个关键差异点
- 对每个差异点: 提供数据和逻辑支撑
- 用表格呈现对比:

| 维度 | 市场共识 | 我们的观点 | 差异原因 |
|------|---------|-----------|---------|
| 营收增长 | X% | Y% | 因为... |

### 3. 什么会改变我们的判断？
- 明确列出1-3个关键信号
- 如果这些信号出现, 我们会重新评估
- 建议读者监控这些指标
"""


def build_consensus_dialogue(kp: KnowledgePackage) -> str:
    """构建与市场共识对话的prompt块"""
    _NL = chr(10)
    
    # Extract any consensus data from data_points
    consensus_points = [dp for dp in kp.data_points 
                       if dp.name.startswith("consensus") or dp.name.startswith("analyst")]
    
    if not consensus_points:
        # If no consensus data available, still include the section structure
        return CONSENSUS_DIALOGUE_PROMPT + """
注意: 当前未获取到一致预期数据。请在报告中明确标注"因数据限制, 本报告未包含完整的市场共识对比分析"。
"""
    
    # Build data table from available consensus points
    table_lines = ["\n| 指标 | 数据 | 来源 |", "|------|------|------|"]
    for dp in consensus_points:
        table_lines.append(f"| {dp.name} | {dp.value} {dp.unit} | {dp.source} |")
    
    return CONSENSUS_DIALOGUE_PROMPT + f"""
### 可用的一致预期数据

以下一致预期数据可用于对比分析:
{_NL.join(table_lines)}
"""
