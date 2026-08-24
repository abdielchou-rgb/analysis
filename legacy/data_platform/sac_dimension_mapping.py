"""sac_dimension_mapping.py — SAC维度 ↔ 数据源映射

每个SAC的每个dimension关联1-2个数据源引擎。
workflow按此映射自动获取数据。

用法:
    from legacy.data_platform.sac_dimension_mapping import get_data_for_dimension, get_dimensions_for_report
    dims = get_dimensions_for_report("industry_deep")
    data = get_data_for_dimension("industry_deep", "profit_pool")
"""

from __future__ import annotations
import logging
from typing import Any, Optional

logger = logging.getLogger("v57.data.sac_mapping")

# SAC类型 → dimension → 数据源引擎函数
MAPPING = {
    "industry_deep": {
        "bold_call": ["eastmoney", "consensus_crawler"],
        "core_disagreement": ["consensus_crawler", "consensus_connector"],
        "profit_pool": ["industry_crawlers", "eastmoney"],
        "supply_demand": ["industry_crawlers", "kline"],
        "competitive": ["industry_crawlers", "eastmoney"],
        "technology": ["industry_crawlers", "news"],
        "market_size": ["industry_crawlers", "consensus_crawler"],
        "policy": ["policy_crawler", "policy_extractor"],
        "capital_market": ["consensus_crawler", "consensus_connector", "eastmoney"],
        "industry_boundary": ["industry_crawlers"],
        "life_cycle": ["industry_crawlers", "macro"],
    },
    "listed_company": {
        "core_disagreement": ["consensus_crawler", "consensus_connector"],
        "business_model": ["eastmoney", "industry_crawlers"],
        "financial_analysis": ["compute_pipeline", "eastmoney"],
        "competitive_position": ["eastmoney", "industry_crawlers"],
        "growth_drivers": ["compute_pipeline", "consensus_crawler"],
        "governance_esg": ["news", "cvc"],
        "valuation_assessment": ["compute_pipeline", "consensus_crawler", "yfinance"],
        "catalyst": ["news", "consensus_crawler"],
        "falsification": ["consensus_crawler", "compute_pipeline"],
    },
    "unlisted_company": {
        "data_declaration": [],
        "company_profile": ["cvc"],
        "funding_history": ["cvc", "news"],
        "business_kpi": ["industry_crawlers", "cvc"],
        "competitive_moat": ["industry_crawlers", "cvc"],
        "valuation_estimate": ["compute_pipeline", "cvc"],
        "exit_analysis": ["cvc", "news"],
        "due_diligence": [],
        "falsification": [],
    },
    "earnings_notes": {
        "core_numbers": ["eastmoney", "consensus_crawler"],
        "surprise_attribution": ["compute_pipeline"],
        "segment_analysis": ["eastmoney", "compute_pipeline"],
        "outlook": ["consensus_crawler", "consensus_connector"],
    },
}

# 数据源ID → 获取函数签名
DATA_SOURCE_FUNCTIONS = {
    "eastmoney": "data.__init__.fetch_realtime",
    "consensus_crawler": "data.consensus_crawler.ConsensusCrawler.fetch",
    "consensus_connector": "data.consensus_connector.fetch_consensus",
    "industry_crawlers": "data.industry_crawlers.fetch_industry_data",
    "policy_crawler": "data.policy_crawler.PolicyCrawlerEngine.fetch",
    "policy_extractor": "data.policy_extractor.PolicyTransmissionExtractor.extract_transmission_chain",
    "compute_pipeline": "core.compute.pipeline.run_compute_pipeline",
    "kline": "data.__init__.fetch_kline",
    "macro": "data.__init__.fetch_macro",
    "news": "data.__init__.fetch_news",
    "cvc": "data.__init__.fetch_cvc",
    "yfinance": "data.__init__.fetch_global_market",
}


def get_dimensions_for_report(report_type: str) -> list[str]:
    """获取某报告类型的所有SAC维度"""
    return list(MAPPING.get(report_type, {}).keys())


def get_data_sources_for_dimension(report_type: str, dimension: str) -> list[str]:
    """获取某维度的数据源列表"""
    return MAPPING.get(report_type, {}).get(dimension, [])


def get_data_for_dimension(report_type: str, dimension: str, asset_code: str = "", industry: str = "") -> list:
    """尝试为指定SAC维度获取数据

    会遍历该维度绑定的所有数据源，返回第一个成功的数据。

    Returns:
        数据点列表，或空列表
    """
    sources = get_data_sources_for_dimension(report_type, dimension)
    if not sources:
        return []

    for source in sources:
        try:
            data = _try_fetch(source, asset_code, industry)
            if data:
                return data
        except Exception as e:
            logger.debug("Data source %s failed for %s/%s: %s", source, report_type, dimension, e)
    return []


def _try_fetch(source: str, asset_code: str, industry: str) -> list:
    """尝试调用某个数据源"""
    if source == "eastmoney":
        from legacy.data_platform.__init__ import fetch_realtime

        if asset_code:
            return fetch_realtime([asset_code])
    elif source == "consensus_crawler":
        from legacy.data_platform.consensus_crawler import ConsensusCrawler

        if asset_code:
            return ConsensusCrawler().fetch(asset_code)
    elif source == "consensus_connector":
        from legacy.data_platform.consensus_connector import fetch_consensus

        if asset_code:
            return fetch_consensus(asset_code)
    elif source == "industry_crawlers":
        from legacy.data_platform.industry_crawlers import fetch_industry_data

        if industry:
            return fetch_industry_data(industry)
    elif source == "compute_pipeline":
        # 需要StructuredData，这里返回空
        return []
    elif source == "macro":
        from legacy.data_platform.__init__ import fetch_macro

        return fetch_macro("all")
    elif source == "news":
        from legacy.data_platform.__init__ import fetch_news

        if asset_code:
            return fetch_news([asset_code]).get(asset_code, [])
    elif source == "cvc":
        from legacy.data_platform.__init__ import fetch_cvc

        if industry:
            return fetch_cvc(sector=industry)
        return fetch_cvc()
    return []


def get_all_mapped_sources() -> list[str]:
    """获取所有已映射的数据源"""
    sources = set()
    for report_type, dims in MAPPING.items():
        for dim, srcs in dims.items():
            for s in srcs:
                sources.add(s)
    return sorted(sources)
