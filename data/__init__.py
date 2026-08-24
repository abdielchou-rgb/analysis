"""V56 Data Pipeline — multi-source financial data, zero API keys.

Data sources:
  - EastMoney HTTP API (realtime quotes) — zero install
  - Tencent Finance K-line — zero install
  - akshare (3000+ interfaces) — pip install akshare
  - yfinance (global markets) — pip install yfinance
  - Policy Crawler (policy/regulation) — pip install crawl4ai
  - CVC/primary market — heuristic + web scrapes
  - Macro (GDP/CPI/PMI/M2) — akshare
  - News/Sentiment — akshare + crawl4ai
  - Satellite (NASA/ESA) — framework
  - CacheEngine (built-in ticker cache)

Usage:
    from data import pipeline
    points = pipeline.fetch(["600519", "300750"])

    # Multi-dimensional data
    from data.data_manager import get_data_manager
    dm = get_data_manager()
    macro = dm.fetch("macro", indicator="gdp")
    policy = dm.fetch("policy", industry="新能源", days=90)
    global_market = dm.fetch("market", assets=["AAPL", "TSLA"])
"""

from __future__ import annotations

import logging
from typing import Optional

from core.models import DataPoint

# Consensus & data source manager
from data.consensus_connector import fetch_consensus
from data.datasource_manager import data_manager, _init_builtin_engines

# Lazy-initialize built-in engines (avoids circular import at module level)
_init_builtin_engines()

logger = logging.getLogger("v56.data")

# Re-export the pipeline singleton from engine
from data.engine import (
    DataPipeline, DataQuery, DataResponse,
    EastMoneyEngine, KLineEngine, CacheEngine,
    pipeline as _pipeline,
)
pipeline = _pipeline

# ═══════════════════════════════════════
# New V56 data engines
# ═══════════════════════════════════════

from data.yfinance_engine import YFinanceEngine

try:
    from data.macro_engine import ChinaMacroEngine
    _HAS_MACRO = True
except ImportError:
    _HAS_MACRO = False

try:
    from data.policy_crawler import PolicyCrawlerEngine
    _HAS_POLICY = True
except ImportError:
    _HAS_POLICY = False

try:
    from data.cvc_engine import CVCEngine
    _HAS_CVC = True
except ImportError:
    _HAS_CVC = False

try:
    from data.news_engine import NewsEngine
    _HAS_NEWS = True
except ImportError:
    _HAS_NEWS = False

try:
    from data.satellite_engine import SatelliteEngine
    _HAS_SATELLITE = True
except ImportError:
    _HAS_SATELLITE = False


# Convenience wrappers
def fetch_realtime(assets: list[str]) -> list[DataPoint]:
    """Fetch realtime market data for one or more stock codes.

    Args:
        assets: List of stock codes, e.g. ["600519", "300750", "AAPL"]

    Returns:
        List of DataPoint objects with price, PE, PB, market cap, etc.
    """
    q = DataQuery(type="market", assets=assets)
    # Try DataSourceManager first (has circuit breaker + retry)
    try:
        resp = data_manager.fetch_with_fallback(q)
        if resp.points:
            return resp.points
    except Exception:
        pass
    # Fallback to pipeline
    resp = _pipeline.fetch(q)
    if resp.error:
        logger.warning(f"fetch_realtime error: {resp.error}")
    return resp.points


def fetch_kline(code: str) -> list:
    """Fetch daily K-line data for a stock code.

    Returns list of [date, open, close, high, low, volume] rows.
    """
    return _pipeline.fetch_kline(code)


def fetch_details(assets: list[str]) -> dict[str, list[DataPoint]]:
    """Fetch from all available engines and return merged results per asset."""
    result: dict[str, list[DataPoint]] = {a: [] for a in assets}
    q = DataQuery(type="market", assets=assets)

    for engine in _pipeline.engines:
        try:
            resp = engine.fetch(q)
            if resp.points:
                for asset in assets:
                    result[asset].extend(resp.points)
        except Exception as e:
            logger.debug(f"Engine {engine.name} failed: {e}")

    return result


# Build a KnowledgePackage-compatible data cache
def build_data_cache(assets: list[str]) -> dict:
    """Build a dict of {asset_code: {metric: value}} for quick KP population."""
    cache = {}
    for code in assets:
        entry = {}
        points = fetch_realtime([code])
        for p in points:
            entry[p.name] = p.value
        cache[code] = entry
    return cache


# ═══════════════════════════════════════
# New V56 convenience wrappers
# ═══════════════════════════════════════

def fetch_macro(indicator: str = "all") -> list[DataPoint]:
    """Fetch China macro-economic data.

    Args:
        indicator: "gdp" | "pmi" | "m2" | "cpi" | "bond" | "all"

    Returns:
        List of DataPoint objects with macro indicators.
    """
    if not _HAS_MACRO:
        logger.warning("macro_engine not available")
        return []
    engine = ChinaMacroEngine()
    resp = engine.fetch(DataQuery(type="macro", assets=[indicator]))
    return resp.points


def fetch_policy(industry: str, days: int = 90) -> list[DataPoint]:
    """Fetch policy/regulation data for an industry.

    Args:
        industry: e.g. "新能源", "半导体", "人工智能"
        days: lookback window

    Returns:
        List of DataPoint objects with policy items.
    """
    if not _HAS_POLICY:
        logger.warning("policy_crawler not available")
        return []
    engine = PolicyCrawlerEngine()
    resp = engine.fetch(DataQuery(
        type="policy", assets=[industry], days=days,
    ))
    return resp.points


def fetch_cvc(company: str = "", sector: str = "") -> list[DataPoint]:
    """Fetch CVC/primary market investment data.

    Args:
        company: Company name for company-level CVC data
        sector: Sector name for sector-level CVC data

    Returns:
        List of DataPoint objects with CVC investment data.
    """
    if not _HAS_CVC:
        logger.warning("cvc_engine not available")
        return []
    engine = CVCEngine()
    if company:
        resp = engine.fetch(DataQuery(type="company_cvc", assets=[company]))
    elif sector:
        resp = engine.fetch(DataQuery(type="sector_cvc", assets=[sector], sector=sector))
    else:
        resp = engine.fetch(DataQuery(type="overview", assets=[]))
    return resp.points


def fetch_news(assets: list[str], days: int = 30) -> dict[str, list[DataPoint]]:
    """Fetch news and announcement data for assets.

    Args:
        assets: Stock codes or company names
        days: Lookback window

    Returns:
        Dict of {asset_code: [DataPoint news items]}
    """
    if not _HAS_NEWS:
        logger.warning("news_engine not available")
        return {}
    engine = NewsEngine()
    result = {}
    for asset in assets:
        resp = engine.fetch(DataQuery(type="news", assets=[asset], days=days))
        result[asset] = resp.points
    return result


def fetch_global_market() -> list[DataPoint]:
    """Fetch global market overview (major indices, commodities)."""
    engine = YFinanceEngine()
    resp = engine.fetch_global_market_overview()
    return resp.points


# Unified data orchestrator
class DataOrchestrator:
    """Unified interface to fetch multi-dimensional data for a report.

    Example:
        dm = DataOrchestrator()
        data = dm.collect("600519", "贵州茅台", "白酒")
        # data contains: market_data, macro, policy, cvc, news, global
    """

    def collect(self, asset_code: str = "", asset_name: str = "",
                industry: str = "") -> dict:
        """Collect all relevant data for a report."""
        result = {}

        # 1. Market data (realtime + fundamentals)
        if asset_code:
            result["market"] = fetch_realtime([asset_code])

        # 2. Consensus estimates
        if asset_code:
            result["consensus"] = fetch_consensus(asset_code)

        # 3. Macro data
        result["macro"] = fetch_macro("all")

        # 4. Policy data
        if industry:
            result["policy"] = fetch_policy(industry)

        # 5. CVC/sector investment data
        if industry:
            result["cvc"] = fetch_cvc(sector=industry)

        # 6. News data
        if asset_code:
            result["news"] = fetch_news([asset_code])

        # 7. Global market overview
        result["global_market"] = fetch_global_market()

        return result


# Export singleton
data_orchestrator = DataOrchestrator()


__all__ = [
    "DataPipeline", "DataQuery", "DataResponse",
    "EastMoneyEngine", "KLineEngine", "CacheEngine",
    "YFinanceEngine",
    "pipeline", "fetch_realtime", "fetch_kline",
    "fetch_details", "build_data_cache",
    "fetch_consensus", "data_manager",
    "fetch_macro", "fetch_policy", "fetch_cvc",
    "fetch_news", "fetch_global_market",
    "DataOrchestrator", "data_orchestrator",
]
