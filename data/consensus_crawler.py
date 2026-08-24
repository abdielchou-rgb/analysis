"""consensus_crawler.py — Crawl4AI 一致预期数据爬虫

替代 akshare 的 EastMoney 接口（不稳定），用 Crawl4AI 爬取新浪财经个股页面
获取机构一致预期数据。

用法:
    from data.consensus_crawler import ConsensusCrawler
    cc = ConsensusCrawler()
    data = cc.fetch("600519")
"""

from __future__ import annotations
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("v57.data.consensus_crawler")

_HAS_CRAWL4AI = False
try:
    from crawl4ai import AsyncWebCrawler
    _HAS_CRAWL4AI = True
except ImportError:
    logger.warning("crawl4ai not installed, consensus_crawler unavailable")

try:
    from core.models import DataPoint
except ImportError:
    from dataclasses import dataclass, field
    @dataclass
    class DataPoint:
        name: str = ""; value: Any = None; unit: str = ""
        source: str = ""; source_level: str = ""; confidence: str = "medium"
        is_estimate: bool = False; fiscal_year: int | None = None; note: str = ""


class ConsensusCrawler:
    name = "consensus_crawler"

    SOURCES = {
        "sina": {"url": "https://vip.stock.finance.sina.com.cn/q/go.php/vReport_List/kind/search/index.phtml?symbol={code}", "type": "analyst_report"},
        "xueqiu": {"url": "https://xueqiu.com/S/{code}", "type": "social_finance"},
    }

    CODE_PREFIX = {"6": "sh", "0": "sz", "3": "sz", "9": "sh", "4": "sz", "8": "bj"}

    def fetch(self, asset_code: str) -> list[DataPoint]:
        if not _HAS_CRAWL4AI:
            logger.warning("crawl4ai not installed, returning empty")
            return []
        try:
            import asyncio
            result = asyncio.run(self._fetch_all(asset_code))
            return result
        except Exception as e:
            logger.error("ConsensusCrawler failed for %s: %s", asset_code, e)
            return []

    async def _fetch_all(self, asset_code: str) -> list[DataPoint]:
        all_points = []
        async with AsyncWebCrawler() as crawler:
            for source_name, config in self.SOURCES.items():
                try:
                    url = config["url"].format(code=asset_code)
                    result = await crawler.arun(url=url, bypass_cache=True)
                    if result.success:
                        text = result.markdown.raw_markdown if hasattr(result.markdown, "raw_markdown") else str(result.markdown)
                        points = self._parse_source(text, source_name, asset_code)
                        all_points.extend(points)
                        logger.info("Crawl4AI %s: %d data points for %s", source_name, len(points), asset_code)
                except Exception as e:
                    logger.debug("Crawl4AI %s failed for %s: %s", source_name, asset_code, e)
                    continue
        if not all_points:
            logger.warning("Crawl4AI returned no data for %s, using mock", asset_code)
            return self._mock_consensus(asset_code)
        return all_points

    def _parse_source(self, text: str, source_name: str, asset_code: str) -> list[DataPoint]:
        points = []
        patterns = {
            "consensus_revenue": [r"营收[^。]*?(\d{3,}\.?\d*)\s*亿", r"营业收入[^。]*?(\d{3,}\.?\d*)\s*亿"],
            "consensus_net_profit": [r"净利润[^。]*?(\d{3,}\.?\d*)\s*亿", r"净利[^。]*?(\d{3,}\.?\d*)\s*亿"],
            "consensus_eps": [r"每股收益[^。]*?(\d+\.?\d*)\s*元", r"EPS[^。]*?(\d+\.?\d*)\s*元"],
            "consensus_pe": [r"市盈率[^。]*?(\d+\.?\d*)", r"PE[^。]*?(\d+\.?\d*)"],
            "analyst_target_avg": [r"目标价[^。]*?(\d+\.?\d*)\s*元"],
            "analyst_buy": [r"买入[^。]*?(\d+)家", r"推荐[^。]*?(\d+)家"],
        }
        units = {"consensus_revenue": "亿", "consensus_net_profit": "亿", "consensus_eps": "元", "consensus_pe": "x", "analyst_target_avg": "元", "analyst_buy": "家"}
        for name, pats in patterns.items():
            val = None
            for pat in pats:
                m = re.search(pat, text)
                if m:
                    val = m.group(1)
                    break
            if val:
                try:
                    v = float(val) if "." in val else int(val)
                    points.append(DataPoint(name=name, value=v, unit=units.get(name, ""),
                                            source=f"crawl4ai/{source_name}", source_level="L2_provider", confidence="medium"))
                except ValueError:
                    pass
        return points

    def _mock_consensus(self, asset_code: str) -> list[DataPoint]:
        return [
            DataPoint(name="consensus_revenue", value=1725.0, unit="亿", source="mock/crawl4ai_fallback", source_level="L3_estimate", confidence="low", note="模拟数据(爬虫不可用)"),
            DataPoint(name="consensus_net_profit", value=870.0, unit="亿", source="mock/crawl4ai_fallback", source_level="L3_estimate", confidence="low"),
            DataPoint(name="consensus_pe", value=22.5, unit="x", source="mock/crawl4ai_fallback", source_level="L3_estimate", confidence="low"),
        ]


def fetch_consensus_crawl4ai(asset_code: str) -> list[DataPoint]:
    cc = ConsensusCrawler()
    return cc.fetch(asset_code)
