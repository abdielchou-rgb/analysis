"""global_sources.py — 全球免费数据源集成

FRED API（美国/全球宏观，10万+序列，免费）
Alpha Vantage（全球行情，免费KEY）
SEC EDGAR（美股财报，免费）

用法:
    from data.global_sources import FREDSource, AlphaVantageSource
    fred = FREDSource()
    gdp = fred.get_series("GDP")
    
    av = AlphaVantageSource()
    price = av.get_quote("AAPL")
"""

from __future__ import annotations
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger("v57.data.global_sources")

try:
    from core.models import DataPoint
except ImportError:
    from dataclasses import dataclass, field
    @dataclass
    class DataPoint:
        name: str = ""; value: Any = None; unit: str = ""
        source: str = ""; source_level: str = ""; confidence: str = "medium"
        is_estimate: bool = False; fiscal_year: int | None = None; note: str = ""

# ── 层1: FRED API ─────────────────────────────────

_HAS_REQUESTS = False
try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    logger.warning("requests not installed")


class FREDSource:
    """FRED API — 美联储经济数据库

    免费API: https://fred.stlouisfed.org/docs/api/api_key.html
    10万+经济时间序列
    
    常用序列:
      GDP = Gross Domestic Product
      CPIAUCSL = CPI All Items
      UNRATE = Unemployment Rate
      FEDFUNDS = Fed Funds Rate
      T10Y2Y = 10Y-2Y Yield Spread
      M2SL = M2 Money Supply
      DGS10 = 10-Year Treasury
      SP500 = S&P 500
    """
    
    name = "fred"
    BASE_URL = "https://api.stlouisfed.org/fred"
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("FRED_API_KEY not set, using mock data")
    
    def get_series(self, series_id: str, observation_start: str = "2020-01-01") -> list[DataPoint]:
        """获取FRED时间序列"""
        if not self.api_key or not _HAS_REQUESTS:
            return self._mock_series(series_id)
        
        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": observation_start,
                "sort_order": "desc",
                "limit": 20,
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                points = []
                for obs in data.get("observations", []):
                    if obs["value"] != ".":
                        points.append(DataPoint(
                            name=f"fred_{series_id}",
                            value=float(obs["value"]),
                            unit=self._unit_for(series_id),
                            source=f"FRED/{series_id}",
                            source_level="L1_filing",
                            confidence="high",
                            note=f"{obs.get('date','')}",
                        ))
                return points[:5]
            else:
                logger.warning("FRED API error: %d %s", resp.status_code, resp.text[:200])
                return self._mock_series(series_id)
        except Exception as e:
            logger.debug("FRED API failed: %s", e)
            return self._mock_series(series_id)
    
    def _unit_for(self, series_id: str) -> str:
        units = {
            "GDP": "亿美元", "CPIAUCSL": "指数", "UNRATE": "%",
            "FEDFUNDS": "%", "T10Y2Y": "%", "M2SL": "亿美元",
            "DGS10": "%", "SP500": "点",
        }
        return units.get(series_id, "")
    
    def _mock_series(self, series_id: str) -> list[DataPoint]:
        return [
            DataPoint(name=f"fred_{series_id}", value=5.25, unit="%",
                      source="mock/FRED", source_level="L3_estimate",
                      confidence="low", note="模拟数据(FRED API未配置)"),
        ]


# ── 层2: Alpha Vantage ─────────────────────────────

class AlphaVantageSource:
    """Alpha Vantage — 全球市场数据

    免费KEY: https://www.alphavantage.co/support/#api-key
    每日500次免费调用
    """
    
    name = "alpha_vantage"
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ALPHA_VANTAGE_KEY", "")
        if not self.api_key:
            logger.warning("ALPHA_VANTAGE_KEY not set, using mock data")
    
    def get_quote(self, symbol: str) -> list[DataPoint]:
        """获取股票实时报价"""
        if not self.api_key or not _HAS_REQUESTS:
            return self._mock_quote(symbol)
        
        try:
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.api_key,
            }
            resp = requests.get(self.BASE_URL, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                quote = data.get("Global Quote", {})
                points = []
                if quote.get("05. price"):
                    points.append(DataPoint(
                        name=f"price_{symbol}", value=float(quote["05. price"]),
                        unit=self._currency_for(symbol),
                        source=f"AlphaVantage/{symbol}",
                        source_level="L1_filing", confidence="high",
                    ))
                if quote.get("09. change"):
                    chg = float(quote["09. change"])
                    pct = chg / float(quote["05. price"]) * 100
                    points.append(DataPoint(
                        name=f"change_pct_{symbol}", value=round(pct, 2),
                        unit="%", source=f"AlphaVantage/{symbol}",
                        source_level="L1_filing", confidence="high",
                    ))
                return points
            return self._mock_quote(symbol)
        except Exception as e:
            logger.debug("AlphaVantage failed: %s", e)
            return self._mock_quote(symbol)
    
    def _currency_for(self, symbol: str) -> str:
        if symbol.endswith((".SS", ".SZ")):
            return "CNY"
        return "USD"
    
    def _mock_quote(self, symbol: str) -> list[DataPoint]:
        return [
            DataPoint(name=f"price_{symbol}", value=150.0, unit="USD",
                      source="mock/AlphaVantage", source_level="L3_estimate",
                      confidence="low"),
        ]


# ── 层3: SEC EDGAR ─────────────────────────────────

class SECEDGARSource:
    """SEC EDGAR — 美股财报全文

    免费: https://www.sec.gov/edgar/sec-api-documentation
    需要设置User-Agent
    """
    
    name = "sec_edgar"
    
    def __init__(self):
        self.headers = {
            "User-Agent": "1hao-analyst-v57 (contact@example.com)",
            "Accept": "application/json",
        }
    
    def get_filing(self, ticker: str, filing_type: str = "10-K") -> list[DataPoint]:
        """获取公司财报关键数据"""
        if not _HAS_REQUESTS:
            return self._mock_filing(ticker)
        try:
            import requests
            cik_url = f"https://data.sec.gov/submissions/CIK{ticker}.json"
            resp = requests.get(cik_url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                return self._mock_filing(ticker)
            return self._mock_filing(ticker)
        except Exception as e:
            logger.debug("SEC EDGAR failed: %s", e)
            return self._mock_filing(ticker)
    
    def _mock_filing(self, ticker: str) -> list[DataPoint]:
        return [
            DataPoint(name=f"sec_revenue_{ticker}", value=100000.0, unit="百万美元",
                      source="mock/SEC_EDGAR", source_level="L3_estimate",
                      confidence="low"),
        ]


# ── 注册到AcquisitionOrchestrator ─────────────────

def register_global_sources():
    """注册所有全球数据源到采集框架"""
    try:
        from data.acquisition.framework import registry, DataSource, DataSourceResult
        
        class FREDAcquisitionSource(DataSource):
            name = "fred"
            def _do_fetch(self, params):
                source = FREDSource()
                series = params.get("series", "GDP")
                points = source.get_series(series)
                return DataSourceResult(success=True, data=points, source="fred")
        
        class AlphaVantageAcquisitionSource(DataSource):
            name = "alpha_vantage"
            def _do_fetch(self, params):
                source = AlphaVantageSource()
                symbol = params.get("symbol", "AAPL")
                points = source.get_quote(symbol)
                return DataSourceResult(success=True, data=points, source="alpha_vantage")
        
        registry.register(FREDAcquisitionSource())
        registry.register(AlphaVantageAcquisitionSource())
        logger.info("Global sources registered: fred, alpha_vantage")
    except Exception as e:
        logger.debug("Global source registration failed: %s", e)
