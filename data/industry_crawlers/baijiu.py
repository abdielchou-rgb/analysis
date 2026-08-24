"""baijiu.py — 白酒行业数据管线

数据源: 微酒(批价), 酒业协会(行业产量/收入), 京东/天猫(终端价格)

用法:
    from data.industry_crawlers.baijiu import fetch_baijiu_data
    data = fetch_baijiu_data()
"""

from __future__ import annotations
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("v57.data.industry.baijiu")

try:
    from core.models import DataPoint
except ImportError:
    from dataclasses import dataclass, field
    @dataclass
    class DataPoint:
        name: str = ""; value: Any = None; unit: str = ""
        source: str = ""; source_level: str = ""; confidence: str = "medium"
        is_estimate: bool = False; fiscal_year: int | None = None; note: str = ""

_HAS_CRAWL4AI = False
try:
    from crawl4ai import AsyncWebCrawler
    _HAS_CRAWL4AI = True
except ImportError:
    logger.warning("crawl4ai not installed, Baijiu data unavailable")


def fetch_baijiu_data() -> list[DataPoint]:
    if not _HAS_CRAWL4AI:
        return _mock_baijiu_data()
    try:
        import asyncio
        return asyncio.run(_fetch_baijiu_async())
    except Exception as e:
        logger.error("Baijiu data fetch failed: %s", e)
        return _mock_baijiu_data()


async def _fetch_baijiu_async() -> list[DataPoint]:
    points = []
    async with AsyncWebCrawler() as crawler:
        urls = [
            "https://www.cnbaijiu.com/",
            "https://www.jiuyetoutiao.com/",
        ]
        for url in urls:
            try:
                result = await crawler.arun(url=url, bypass_cache=True)
                if result.success:
                    text = result.markdown.raw_markdown if hasattr(result.markdown, "raw_markdown") else str(result.markdown)
                    parsed = _parse_baijiu_page(text)
                    points.extend(parsed)
            except Exception as e:
                logger.debug("Baijiu crawl failed for %s: %s", url, e)
    if not points:
        return _mock_baijiu_data()
    return points


def _parse_baijiu_page(text: str) -> list[DataPoint]:
    points = []
    patterns = {
        "maotai_batch_price": [(r"飞天茅台[^。]*?(\d+\.?\d*)\s*元"), (r"茅台批价[^。]*?(\d+\.?\d*)")],
        "baijiu_industry_revenue": [(r"白酒[^。]*?收入[^。]*?(\d+\.?\d*)\s*亿"), (r"白酒[^。]*?营收[^。]*?(\d+\.?\d*)\s*亿")],
        "baijiu_industry_profit": [(r"白酒[^。]*?利润[^。]*?(\d+\.?\d*)\s*亿")],
        "baijiu_industry_output": [(r"白酒[^。]*?产量[^。]*?(\d+\.?\d*)\s*万[千]?升")],
    }
    units = {"maotai_batch_price": "元/瓶", "baijiu_industry_revenue": "亿元", "baijiu_industry_profit": "亿元", "baijiu_industry_output": "万千升"}
    for name, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text)
            if m:
                try:
                    points.append(DataPoint(name=name, value=float(m.group(1)), unit=units.get(name, ""),
                                            source="crawl4ai/baijiu", source_level="L2_provider", confidence="medium"))
                except ValueError:
                    pass
                break
    return points


def _mock_baijiu_data() -> list[DataPoint]:
    return [
        DataPoint(name="maotai_batch_price", value=2450.0, unit="元/瓶", source="mock/微酒", source_level="L3_estimate", confidence="low", note="模拟数据(爬虫不可用)"),
        DataPoint(name="baijiu_industry_revenue", value=7560.0, unit="亿元", source="mock/酒业协会", source_level="L3_estimate", confidence="low"),
        DataPoint(name="baijiu_industry_profit", value=2380.0, unit="亿元", source="mock/酒业协会", source_level="L3_estimate", confidence="low"),
    ]
