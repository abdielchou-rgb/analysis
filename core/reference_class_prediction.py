"""基准率预测模块（Reference Class Forecasting）

Kahneman & Tversky 的核心洞见：人类在做预测时会忽略基准率，
因为在每个案例上编故事比查统计数据更自然。
但数据证明，基准率预测比"直觉+故事"准确得多。

2hao 集成方式：
  在 unlisted_company 分析的估值与退出逻辑链中注入基准率参考。
  数据来源：行业统计、VC/PE 回报数据库、公开市场成功率分析。
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.reference_class")

# ── 基准率数据库（初始核心数据，可扩展）──

# 按阶段的基准成功率
STAGE_BASERATES = {
    "种子轮": {"survival_5yr": 0.10, "exit_positive": 0.03, "unicorn": 0.001},
    "天使轮": {"survival_5yr": 0.15, "exit_positive": 0.05, "unicorn": 0.002},
    "A轮": {"survival_5yr": 0.25, "exit_positive": 0.10, "unicorn": 0.005},
    "B轮": {"survival_5yr": 0.35, "exit_positive": 0.18, "unicorn": 0.015},
    "C轮": {"survival_5yr": 0.50, "exit_positive": 0.28, "unicorn": 0.03},
    "D轮+": {"survival_5yr": 0.65, "exit_positive": 0.40, "unicorn": 0.06},
    "Pre-IPO": {"survival_5yr": 0.80, "exit_positive": 0.60, "unicorn": 0.10},
}

# 按行业的 5 年存活率
INDUSTRY_BASERATES = {
    "企业服务/SaaS": {"survival_5yr": 0.30, "median_exit_value": 50000000, "exit_to_ipo_ratio": 0.02},
    "消费互联网": {"survival_5yr": 0.15, "median_exit_value": 80000000, "exit_to_ipo_ratio": 0.01},
    "硬科技/半导体": {"survival_5yr": 0.40, "median_exit_value": 150000000, "exit_to_ipo_ratio": 0.05},
    "生物医药": {"survival_5yr": 0.20, "median_exit_value": 200000000, "exit_to_ipo_ratio": 0.03},
    "金融科技": {"survival_5yr": 0.25, "median_exit_value": 100000000, "exit_to_ipo_ratio": 0.03},
    "人工智能": {"survival_5yr": 0.22, "median_exit_value": 120000000, "exit_to_ipo_ratio": 0.04},
    "新能源/清洁科技": {"survival_5yr": 0.35, "median_exit_value": 90000000, "exit_to_ipo_ratio": 0.04},
    "消费品牌": {"survival_5yr": 0.20, "median_exit_value": 60000000, "exit_to_ipo_ratio": 0.01},
    "教育科技": {"survival_5yr": 0.18, "median_exit_value": 40000000, "exit_to_ipo_ratio": 0.01},
    "物流/供应链": {"survival_5yr": 0.30, "median_exit_value": 70000000, "exit_to_ipo_ratio": 0.02},
}

# 创始人背景与成功概率的调整系数
FOUNDER_ADJUSTMENTS = {
    "连续创业者(成功退出)": 1.8,
    "连续创业者(未退出)": 1.2,
    "行业资深(10年+)": 1.5,
    "顶级机构背书": 1.4,
    "名校/名企背景": 1.2,
    "首次创业者(无行业经验)": 0.6,
    " solo-founder": 0.5,
}


@dataclass
class ReferenceClassResult:
    """基准率预测结果"""

    stage: str = ""
    industry: str = ""
    base_survival_rate: float = 0.0
    adjusted_survival_rate: float = 0.0
    median_exit_value: float = 0.0
    exit_proba: float = 0.0
    founder_adjustment: float = 1.0
    comparable_companies: list = field(default_factory=list)
    confidence: str = "medium"  # high / medium / low


def get_baserate(stage: str = "", industry: str = "", founder_profile: str | None = None) -> ReferenceClassResult:
    """获取基准率预测"""
    result = ReferenceClassResult(stage=stage, industry=industry)

    # 按阶段
    stage_data = STAGE_BASERATES.get(stage, {})
    result.base_survival_rate = stage_data.get("survival_5yr", 0.15)
    result.exit_proba = stage_data.get("exit_positive", 0.05)

    # 按行业调整
    industry_data = INDUSTRY_BASERATES.get(industry, {})
    if industry_data:
        industry_survival = industry_data.get("survival_5yr", 0.20)
        # 混合基准率：阶段基准和行业基准的几何平均
        result.base_survival_rate = (result.base_survival_rate * industry_survival) ** 0.5
        result.median_exit_value = industry_data.get("median_exit_value", 50000000)
        result.exit_proba = max(result.exit_proba, industry_data.get("exit_to_ipo_ratio", 0.02))

    # 创始人调整
    if founder_profile and founder_profile in FOUNDER_ADJUSTMENTS:
        result.founder_adjustment = FOUNDER_ADJUSTMENTS[founder_profile]
        result.adjusted_survival_rate = min(1.0, result.base_survival_rate * result.founder_adjustment)
    else:
        result.adjusted_survival_rate = result.base_survival_rate

    result.confidence = "low" if not stage else "medium"
    if stage and industry:
        result.confidence = "medium"
    if stage and industry and founder_profile:
        result.confidence = "high"

    return result


def baserate_to_prompt(result: ReferenceClassResult) -> str:
    """生成基准率提示文本，注入 LLM prompt"""
    lines = ["[基准率预测参考]"]
    lines.append(f"  阶段: {result.stage or '未知'}")
    lines.append(f"  行业: {result.industry or '未知'}")
    lines.append(f"  类似公司5年存活率: {result.base_survival_rate * 100:.0f}%")
    if result.founder_adjustment != 1.0:
        lines.append(
            f"  创始人调整系数: {result.founder_adjustment:.1f}x → 调整后存活率: {result.adjusted_survival_rate * 100:.0f}%"
        )
    lines.append(f"  正回报退出概率: {result.exit_proba * 100:.0f}%")
    if result.median_exit_value:
        lines.append(f"  同类公司退出估值中位数: {result.median_exit_value / 1e8:.1f}亿")
    lines.append(f"  置信度: {result.confidence}")
    lines.append("[/基准率参考]")
    return "\n".join(lines)
