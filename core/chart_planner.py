"""chart_planner.py — SAC驱动的图表规划器

根据报告类型（行业/上市/非上市/财报）和SAC维度，自动生成图表规划。
每种报告类型有预定义的图表组合策略。

用法:
    from core.chart_planner import ChartPlanner
    planner = ChartPlanner()
    plan = planner.plan("industry_deep", {"profit_pool": True, "supply_demand": True})
    # plan: [{"type": "bar", "title": "...", "dimension": "profit_pool"}, ...]
"""

from __future__ import annotations
from core.cn_font_setup import setup_cn_font, get_cn_font
setup_cn_font()  # Initialize Chinese font support
import logging
from typing import Any, Optional

logger = logging.getLogger("v57.chart_planner")


# 报告类型 → 图表策略
CHART_STRATEGIES = {
    "industry_deep": {
        "min_charts": 6,
        "target_charts": 10,
        "charts": [
            {"type": "bar", "title": "产业链利润池分布", "dimension": "profit_pool",
             "desc": "各环节毛利率/净利率对比", "mandatory": True},
            {"type": "waterfall", "title": "利润池变迁归因", "dimension": "profit_pool",
             "desc": "利润在产业链各环节之间的迁移", "mandatory": True},
            {"type": "line", "title": "供需平衡表", "dimension": "supply_demand",
             "desc": "近3年+预测2年供需变化", "mandatory": True},
            {"type": "heatmap", "title": "敏感性矩阵", "dimension": "capital_market",
             "desc": "估值对关键变量的敏感性", "mandatory": True},
            {"type": "radar", "title": "竞争格局雷达", "dimension": "competitive",
             "desc": "主要竞争对手多维评分", "mandatory": False},
            {"type": "bar", "title": "市场份额格局", "dimension": "competitive",
             "desc": "前5大玩家市占率对比", "mandatory": True},
            {"type": "line", "title": "技术路线演进", "dimension": "technology",
             "desc": "各技术路线渗透率趋势", "mandatory": True},
            {"type": "bar", "title": "市场空间拆解", "dimension": "market_size",
             "desc": "TAM/SAM/SOM拆解", "mandatory": True},
            {"type": "line", "title": "资本市场定价", "dimension": "capital_market",
             "desc": "行业PE Band / PB Band", "mandatory": True},
            {"type": "pareto", "title": "政策传导分析", "dimension": "policy",
             "desc": "各政策影响力度帕累托", "mandatory": False},
        ],
    },
    "listed_company": {
        "min_charts": 5,
        "target_charts": 8,
        "charts": [
            {"type": "waterfall", "title": "营收桥(收入分解)", "dimension": "financial_analysis",
             "desc": "量/价/结构对营收变化的贡献", "mandatory": True},
            {"type": "waterfall", "title": "毛利桥(利润归因)", "dimension": "financial_analysis",
             "desc": "毛利率变化的驱动因素", "mandatory": True},
            {"type": "bar", "title": "ROE拆解(Dupont)", "dimension": "financial_analysis",
             "desc": "杜邦分析三层拆解", "mandatory": True},
            {"type": "tornado", "title": "估值敏感度龙卷风", "dimension": "valuation_assessment",
             "desc": "各驱动因素对DCF估值影响", "mandatory": True},
            {"type": "bar", "title": "可比估值矩阵", "dimension": "valuation_assessment",
             "desc": "PE/PB/PS/EV/EBITDA对标", "mandatory": True},
            {"type": "radar", "title": "竞争多维评分", "dimension": "competitive_position",
             "desc": "与可比公司的多维对比", "mandatory": False},
            {"type": "line", "title": "增长驱动趋势", "dimension": "growth_drivers",
             "desc": "核心增长指标时间序列", "mandatory": True},
            {"type": "line", "title": "股价与催化剂", "dimension": "catalyst",
             "desc": "历史股价+关键事件标注", "mandatory": False},
        ],
    },
    "unlisted_company": {
        "min_charts": 4,
        "target_charts": 6,
        "charts": [
            {"type": "bar", "title": "估值三角验证", "dimension": "valuation_estimate",
             "desc": "最近融资/可比/场景三个独立估值口径", "mandatory": True},
            {"type": "bar", "title": "可比估值对标", "dimension": "valuation_estimate",
             "desc": "对标上市可比公司PS/PE", "mandatory": True},
            {"type": "radar", "title": "竞争壁垒评估", "dimension": "competitive_moat",
             "desc": "技术/品牌/网络效应/规模/许可多维评估", "mandatory": True},
            {"type": "line", "title": "融资路线图", "dimension": "funding_history",
             "desc": "各轮估值与融资金额趋势", "mandatory": True},
            {"type": "bar", "title": "单位经济拆解", "dimension": "business_kpi",
             "desc": "CAC/LTV/毛利率关键指标", "mandatory": False},
            {"type": "bar", "title": "退出路径对比", "dimension": "exit_analysis",
             "desc": "IPO/并购/老股转让可行性评分", "mandatory": False},
        ],
    },
    "earnings_notes": {
        "min_charts": 3,
        "target_charts": 4,
        "charts": [
            {"type": "bar", "title": "核心数字一览", "dimension": "core_numbers",
             "desc": "营收/利润/利润率 vs 一致预期", "mandatory": True},
            {"type": "waterfall", "title": "超预期归因", "dimension": "surprise_attribution",
             "desc": "超预期/不及预期的驱动因素", "mandatory": True},
            {"type": "line", "title": "分部趋势", "dimension": "segment_analysis",
             "desc": "各业务分部的收入/利润趋势", "mandatory": True},
            {"type": "tornado", "title": "展望敏感度", "dimension": "outlook",
             "desc": "下季度指引的敏感性分析", "mandatory": False},
        ],
    },
}

# 默认策略（降级）
DEFAULT_STRATEGY = {
    "min_charts": 3,
    "target_charts": 5,
    "charts": [
        {"type": "bar", "title": "核心指标一览", "dimension": "", "desc": "", "mandatory": True},
        {"type": "pie", "title": "构成分析", "dimension": "", "desc": "", "mandatory": True},
        {"type": "line", "title": "趋势分析", "dimension": "", "desc": "", "mandatory": True},
    ],
}


class ChartPlanner:
    """根据SAC报告类型规划图表集"""

    def __init__(self):
        self.strategies = CHART_STRATEGIES

    def plan(self, report_type: str, available_dimensions: dict | None = None,
             data_available: bool = True) -> dict:
        """生成图表规划

        Args:
            report_type: industry_deep / listed_company / unlisted_company / earnings_notes
            available_dimensions: 可用的SAC维度（用于筛选可生成的图表）
            data_available: 是否有数据支撑

        Returns:
            {"charts": [...], "min_charts": N, "target_charts": N, "strategy": "..."}
        """
        strategy = self.strategies.get(report_type, DEFAULT_STRATEGY)

        # 筛选可生成的图表
        available = []
        for c in strategy["charts"]:
            # 如果有可用维度过滤
            if available_dimensions and c.get("dimension"):
                if c["dimension"] not in available_dimensions:
                    if c.get("mandatory"):
                        # 必选图表即使数据暂缺也要规划
                        available.append(c)
                    continue
            available.append(c)

        # 确保至少包含所有mandatory图表
        mandatory = [c for c in available if c.get("mandatory")]
        optional = [c for c in available if not c.get("mandatory")]

        # 如果量不够，补充optional
        if len(mandatory) < strategy["min_charts"]:
            needed = strategy["min_charts"] - len(mandatory)
            available = mandatory + optional[:needed]
        else:
            available = mandatory + optional[:max(0, strategy["target_charts"] - len(mandatory))]

        return {
            "charts": available,
            "min_charts": strategy["min_charts"],
            "target_charts": strategy["target_charts"],
            "strategy": report_type,
            "chart_count": len(available),
        }

    def get_min_charts(self, report_type: str) -> int:
        """获取该报告类型的最小图表数"""
        return self.strategies.get(report_type, DEFAULT_STRATEGY)["min_charts"]

    def get_target_charts(self, report_type: str) -> int:
        """获取该报告类型的目标图表数"""
        return self.strategies.get(report_type, DEFAULT_STRATEGY)["target_charts"]


# 单例
chart_planner = ChartPlanner()
