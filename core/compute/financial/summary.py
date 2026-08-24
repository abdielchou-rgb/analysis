"""
1号分析师 V30 — 财务摘要模型

从 StructuredData 提取关键财务指标，输出为可供报告直接使用的 FinancialSummary。
"""

from __future__ import annotations

from core.models import FinancialSummary, StructuredData


def build_financial_summary(data: StructuredData) -> FinancialSummary:
    """
    从结构化数据构建财务摘要。

    Args:
        data: L1 输出的结构化数据

    Returns:
        FinancialSummary: 可直接渲染为 Markdown 表格的财务摘要
    """
    financials = sorted(data.financials, key=lambda x: x.fiscal_year)
    years = [f.fiscal_year for f in financials]

    items = {}

    # 营收 (亿元)
    items["营收(亿元)"] = {str(f.fiscal_year): f.revenue for f in financials}

    # 归母净利润 (亿元)
    items["归母净利润(亿元)"] = {str(f.fiscal_year): f.net_profit for f in financials}

    # 毛利率 (%)
    items["毛利率(%)"] = {str(f.fiscal_year): f.gross_margin for f in financials}

    # 净利率 (%)
    items["净利率(%)"] = {str(f.fiscal_year): f.net_margin for f in financials}

    # ROE (%)
    items["ROE(%)"] = {str(f.fiscal_year): f.roe for f in financials}

    # 营收同比增速 (%)
    items["营收增速(%)"] = {str(f.fiscal_year): f.yoy_revenue for f in financials}

    # 净利润同比增速 (%)
    items["净利增速(%)"] = {str(f.fiscal_year): f.yoy_net_profit for f in financials}

    # 每股收益
    items["EPS"] = {str(f.fiscal_year): f.eps for f in financials}

    # 资产负债率 (%)
    items["资产负债率(%)"] = {
        str(f.fiscal_year): f.liability_to_asset for f in financials
    }

    # 利润含金量 (经营现金流/净利润)
    items["利润含金量"] = {
        str(f.fiscal_year): f.cfo_to_net_profit for f in financials
    }

    # 总资产周转率
    items["总资产周转率"] = {
        str(f.fiscal_year): f.asset_turnover_ratio for f in financials
    }

    return FinancialSummary(
        company=data.profile.stock_name,
        years=years,
        items=items,
    )
