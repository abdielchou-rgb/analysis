"""
V53 Standardized Appendix — 报告附录模板

每个报告末尾的标准化附录: 方法论说明 + 财务摘要 + 风险因素 + 评级体系 + 术语表 + 免责声明
"""

from core.models import KnowledgePackage


def build_appendix(kp: KnowledgePackage) -> dict[str, str]:
    """生成标准化的附录内容"""

    # 评级体系
    rating_system = """
### 评级体系说明

| 评级 | 含义 |
|------|------|
| **买入 (Buy)** | 预期未来12个月绝对回报 > 15% |
| **增持 (Accumulate)** | 预期未来12个月绝对回报 5%-15% |
| **中性 (Neutral)** | 预期未来12个月绝对回报 -5%-5% |
| **减持 (Reduce)** | 预期未来12个月绝对回报 -15%-5% |
| **卖出 (Sell)** | 预期未来12个月绝对回报 < -15% |

**风险评级**:
| 风险等级 | 含义 |
|---------|------|
| 低风险 | 公司经营稳定, 行业可预测性高 |
| 中风险 | 公司或行业存在一定不确定性 |
| 高风险 | 公司或行业面临重大不确定因素 |
"""

    # 方法论说明
    methodology = """
### 估值方法论

本报告采用的估值方法包括但不限于:

- **DCF估值**: 以自由现金流折现模型为基础, 结合WACC和终端增长率假设
- **可比估值**: 参考同行业可比公司的PE/PB/EV/EBITDA等估值指标
- **SOTP估值**: 对多元化业务公司采用分部加总法
- **NAV估值**: 适用于房地产、资源类公司

关键假设:
- WACC基于CAPM模型计算, 无风险利率参考10年期国债收益率
- 终端增长率假设参考行业长期增长率与GDP增速
- 可比公司选取标准: 业务相似性、市值规模、市场定位
"""

    # 数据来源
    data_sources = """
### 数据来源说明

| 数据类型 | 来源 | 可信度 |
|---------|------|-------|
| 财务数据 | akshare / Wind / 公司公告 | 高 |
| 一致预期 | akshare 分析师预测 | 中 |
| 行业数据 | 行业协会 / IDC / 公开报告 | 中 |
| 估值模型 | 130家估值模型批量提取 | 中-高 |
| 可比分析 | 公开市场数据 | 中 |
"""

    # 风险因素
    risk_factors = """
### 一般风险因素

- **市场风险**: 宏观经济波动、利率变化、汇率波动可能影响公司估值
- **行业风险**: 行业政策变化、技术迭代、竞争加剧
- **公司风险**: 管理层变动、核心人才流失、业务集中度
- **财务风险**: 杠杆率变化、现金流波动、资产减值
"""

    # 术语表
    glossary = """
### 术语表

| 术语 | 定义 |
|------|------|
| CAGR | 复合年增长率 (Compound Annual Growth Rate) |
| WACC | 加权平均资本成本 (Weighted Average Cost of Capital) |
| DCF | 现金流折现模型 (Discounted Cash Flow) |
| SOTP | 分部加总法 (Sum of The Parts) |
| EBITDA | 息税折旧摊销前利润 |
| PE | 市盈率 (Price to Earnings Ratio) |
| PB | 市净率 (Price to Book Ratio) |
| ROE | 净资产收益率 (Return on Equity) |
| Conviction | 置信度评分, 反映对投资判断的信心程度 |
"""

    # 免责声明
    disclaimer = """
### 免责声明

本报告基于公开信息及行业研究数据编写, 所有数据均标注来源。报告中的分析和判断仅为研究视角的呈现, 不构成任何形式的投资建议。

**预测的不确定性**: 报告中包含的盈利预测、估值假设和情景分析基于当前可获取的信息。实际结果可能与预测存在重大差异。

**利益冲突申明**: 报告撰写方可能与所分析的公司存在业务关系。

**版权声明**: 本报告版权归撰写方所有。未经书面许可, 不得复制、传播或使用本报告内容。
"""

    return {
        "rating_system": rating_system,
        "methodology": methodology,
        "data_sources": data_sources,
        "risk_factors": risk_factors,
        "glossary": glossary,
        "disclaimer": disclaimer,
    }
