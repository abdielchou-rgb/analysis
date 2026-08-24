# Search Planner — 基于SAC维度自动生成搜索查询
# 让Tavily/Playwright做更有针对性的搜索，而不是泛泛搜一次

from __future__ import annotations
from typing import Optional

# SAC维度 → 搜索策略
SAC_SEARCH_MAP = {
    "core_disagreement": {
        "queries": [
            "市场共识 分歧 预期差 最新",
            "bullish bearish case recent",
            "analyst consensus estimate revision",
        ],
        "priority": 1,
        "depth": "advanced",
    },
    "business_model": {
        "queries": [
            "商业模式 护城河 竞争优势 分析",
            "business model competitive advantage",
            "unit economics margin structure",
        ],
        "priority": 1,
        "depth": "advanced",
    },
    "competitive_position": {
        "queries": [
            "竞争格局 市场份额 排名",
            "competitor analysis market share",
            "industry landscape competitive dynamics",
        ],
        "priority": 2,
        "depth": "basic",
    },
    "financial_analysis": {
        "queries": [
            "财务分析 ROE 杜邦 分析",
            "financial analysis recent earnings",
            "revenue breakdown segment trend",
        ],
        "priority": 2,
        "depth": "basic",
    },
    "growth_drivers": {
        "queries": [
            "增长驱动 未来增长 看点",
            "growth drivers future catalysts",
            "new product pipeline expansion",
        ],
        "priority": 2,
        "depth": "advanced",
    },
    "catalyst": {
        "queries": [
            "催化剂 股价驱动 近期事件",
            "stock catalysts upcoming events",
            "product launch regulatory approval",
        ],
        "priority": 1,
        "depth": "advanced",
    },
    "falsification": {
        "queries": [
            "风险 不确定性 潜在问题",
            "risks headwinds challenges",
            "bear case downside risks",
        ],
        "priority": 3,
        "depth": "basic",
    },
    "valuation_assessment": {
        "queries": [
            "估值 目标价 评级 调整",
            "valuation target price rating change",
            "DCF implied value sum-of-parts",
        ],
        "priority": 1,
        "depth": "advanced",
    },
    "governance_esg": {
        "queries": [
            "管理层 治理 ESG 评价",
            "management quality governance ESG",
            "insider trading shareholder return",
        ],
        "priority": 3,
        "depth": "basic",
    },
    "industry_deep": {
        "queries": [
            "行业深度 产业链 市场空间",
            "industry deep dive TAM market size",
            "industry trends technology roadmap",
        ],
        "priority": 1,
        "depth": "advanced",
    },
}

# 行业专用搜索词
INDUSTRY_QUERIES = {
    "半导体": ["芯片 国产替代 产能 扩产 良率 制程"],
    "白酒": ["白酒 动销 库存 批价 提价 渠道"],
    "新能源": ["锂电 光伏 储能 装机 产能过剩 价格"],
    "医药": ["创新药 集采 管线 FDA 批准 临床"],
    "互联网": ["用户增长 ARPU 渗透率 监管 竞争"],
    "消费": ["消费趋势 渗透率 渠道 品牌 份额"],
    "金融": ["净息差 不良率 财富管理 监管"],
}


def plan_queries(asset: str, report_type: str = "listed_company",
                 industry: str = "") -> list[dict]:
    """根据报告类型和资产信息，生成搜索查询计划"""
    queries = []

    # 1. 通用资产搜索
    if asset:
        queries.append({
            "query": f"{asset} 最新消息 财务数据 分析",
            "depth": "advanced",
            "max_results": 8,
            "reason": "通用资产信息",
        })
        queries.append({
            "query": f"{asset} stock analysis forecast target price",
            "depth": "advanced",
            "max_results": 5,
            "reason": "国际视角",
        })

    # 2. 行业专搜
    if industry:
        for key, ind_queries in INDUSTRY_QUERIES.items():
            if key in industry:
                for q in ind_queries:
                    queries.append({
                        "query": f"{asset} {q}",
                        "depth": "advanced",
                        "max_results": 5,
                        "reason": f"行业深度: {key}",
                    })
                break

    # 3. SAC维度搜索 (取前3个最高优的维度)
    sac_dims = list(SAC_SEARCH_MAP.keys())
    for dim in sac_dims[:3]:
        config = SAC_SEARCH_MAP[dim]
        for q in config["queries"][:1]:
            full_q = f"{asset} {q}" if asset else q
            queries.append({
                "query": full_q,
                "depth": config["depth"],
                "max_results": config.get("max_results", 5),
                "reason": f"SAC维度: {dim}",
            })

    return queries


def plan_macro_queries() -> list[dict]:
    """宏观搜索查询"""
    return [
        {"query": "中国宏观经济 最新数据 政策方向 PMI", "depth": "advanced", "max_results": 3, "reason": "宏观定位"},
        {"query": "China macro economy policy outlook GDP", "depth": "basic", "max_results": 3, "reason": "国际宏观"},
        {"query": "行业政策 最新 产业新闻 监管", "depth": "basic", "max_results": 3, "reason": "政策动态"},
    ]