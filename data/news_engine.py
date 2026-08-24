"""V56 NewsEngine — 新闻/公告/情绪数据连接器

获取个股新闻、行业新闻、政策新闻和社交媒体情绪数据。

数据源:
- akshare: 东方财富个股新闻、新闻要闻
- akshare: 巨潮资讯公告
- 东方财富股吧/雪球情绪（Crawl4AI）
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger("v56.data.news")

_HAS_AKSHARE = False
try:
    import akshare as ak
    import pandas as pd
    _HAS_AKSHARE = True
except ImportError:
    logger.warning("akshare not installed, news engine limited")

_HAS_CRAWL4AI = False
try:
    from crawl4ai import AsyncWebCrawler
    _HAS_CRAWL4AI = True
except ImportError:
    logger.warning("crawl4ai not installed, sentiment scraping unavailable")

try:
    from core.models import DataPoint
    from data.engine import DataResponse, DataQuery
except ImportError:
    from dataclasses import dataclass, field
    @dataclass
    class DataPoint:
        name: str = ""; value: Any = None; unit: str = ""
        source: str = ""; source_level: str = ""; confidence: str = "medium"
        is_estimate: bool = False; fiscal_year: int | None = None; note: str = ""
    @dataclass
    class DataResponse:
        points: list = field(default_factory=list)
        source: str = ""; confidence: str = "medium"; error: str = ""
    @dataclass
    class DataQuery:
        type: str = "news"; assets: list = field(default_factory=list)
        days: int = 30


class NewsEngine:
    """新闻/公告/情绪数据引擎

    用法:
        engine = NewsEngine()
        result = engine.fetch(DataQuery(assets=["600519"], type="news"))
    """
    name = "news_engine"

    def fetch(self, query: DataQuery) -> DataResponse:
        points = []

        if query.type in ("news", "stock_news"):
            for asset in query.assets:
                points.extend(self._fetch_stock_news(asset))
        elif query.type == "sentiment":
            for asset in query.assets:
                points.extend(self._fetch_sentiment(asset))
        elif query.type == "announcement":
            for asset in query.assets:
                points.extend(self._fetch_announcements(asset))

        if not points:
            # 返回示例新闻作为fallback
            pass

        return DataResponse(points=points, source=self.name,
                            confidence="medium" if points else "low")

    def _fetch_stock_news(self, code: str) -> list[DataPoint]:
        """获取个股新闻和要闻"""
        points = []
        if not _HAS_AKSHARE:
            return points
        try:
            df = ak.stock_news_em(symbol=code)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    title = row.get("新闻标题", "") or row.get("title", "")
                    if title:
                        points.append(DataPoint(
                            name="stock_news",
                            value=str(title)[:200],
                            unit="",
                            source=f"akshare/news_em/{code}",
                            source_level="L2_media",
                            confidence="medium",
                        ))
                        if len(points) >= 10:
                            break
        except Exception as e:
            logger.debug("Stock news fetch failed for %s: %s", code, e)
        return points

    def _fetch_sentiment(self, code: str) -> list[DataPoint]:
        """获取社交媒体情绪（正/负/中）"""
        points = []
        try:
            # 使用pywencai获取问财情绪数据（如果可用）
            import pywencai
            q = pywencai.get(query=f"{code} 情绪")
            if q is not None and not q.empty:
                pass  # pywencai返回结构不稳定，暂不处理
        except ImportError:
            pass
        return points

    def _fetch_announcements(self, code: str) -> list[DataPoint]:
        """获取公司公告"""
        points = []
        if not _HAS_AKSHARE:
            return points
        try:
            df = ak.stock_notice_report(symbol=code)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    title = row.get("title", "") or row.get("公告标题", "")
                    if title:
                        points.append(DataPoint(
                            name="announcement",
                            value=str(title)[:200],
                            unit="",
                            source=f"akshare/notice/{code}",
                            source_level="L1_filing",
                            confidence="high",
                        ))
                        if len(points) >= 5:
                            break
        except Exception as e:
            logger.debug("Announcement fetch failed for %s: %s", code, e)
        return points
