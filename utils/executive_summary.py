"""
V53 Executive Summary — 执行摘要模板

报告第一页的结构化输出模板: 投资论点 + 关键指标表 + 评级 + Conviction 评分。
"""

EXECUTIVE_SUMMARY_TEMPLATE = """
## 执行摘要（第一页）

### 投资论点

{investment_thesis}

### 关键指标表

| 指标 | 数据 | 说明 |
|------|------|------|
| 当前股价 | {current_price} | {price_date} |
| 目标价 (Base) | {base_target} | 上行空间 {upside_pct} |
| 目标价 (Bull) | {bull_target} | 上行空间 {bull_upside} |
| 目标价 (Bear) | {bear_target} | 下行空间 {downside_pct} |
| 评级 | {rating} | {conviction_level} |
| Conviction 评分 | {conviction_score}/100 | {conviction_label} |

### 核心假设

| 假设 | 值 | 行业对标 |
|------|---|---------|
| 营收CAGR (3年) | {revenue_cagr} | {cagr_benchmark} |
| 毛利率 | {gross_margin} | {gm_benchmark} |
| WACC | {wacc} | {wacc_benchmark} |
| 终端增长率 | {terminal_growth} | {tg_benchmark} |

### 投资亮点

{highlights}

### 关键风险

{key_risks}

### 催化剂时间表

{catalysts}
"""


def format_executive_summary(kwargs: dict) -> str:
    """填充执行摘要模板"""
    return EXECUTIVE_SUMMARY_TEMPLATE.format(
        investment_thesis=kwargs.get("investment_thesis", "待补充"),
        current_price=kwargs.get("current_price", "待补充"),
        price_date=kwargs.get("price_date", "待补充"),
        base_target=kwargs.get("base_target", "待补充"),
        upside_pct=kwargs.get("upside_pct", "待补充"),
        bull_target=kwargs.get("bull_target", "待补充"),
        bull_upside=kwargs.get("bull_upside", "待补充"),
        bear_target=kwargs.get("bear_target", "待补充"),
        downside_pct=kwargs.get("downside_pct", "待补充"),
        rating=kwargs.get("rating", "未评级"),
        conviction_level=kwargs.get("conviction_level", "中等"),
        conviction_score=kwargs.get("conviction_score", 50),
        conviction_label=kwargs.get("conviction_label", "中等置信度"),
        revenue_cagr=kwargs.get("revenue_cagr", "待补充"),
        cagr_benchmark=kwargs.get("cagr_benchmark", "无对标"),
        gross_margin=kwargs.get("gross_margin", "待补充"),
        gm_benchmark=kwargs.get("gm_benchmark", "无对标"),
        wacc=kwargs.get("wacc", "待补充"),
        wacc_benchmark=kwargs.get("wacc_benchmark", "无对标"),
        terminal_growth=kwargs.get("terminal_growth", "待补充"),
        tg_benchmark=kwargs.get("tg_benchmark", "无对标"),
        highlights=kwargs.get("highlights", "待补充"),
        key_risks=kwargs.get("key_risks", "待补充"),
        catalysts=kwargs.get("catalysts", "待补充"),
    )
