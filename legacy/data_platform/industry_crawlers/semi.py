"""semi.py — 半导体行业数据管线

数据源: WSTS(全球销售额), SEMI(资本支出), 芯思想(中国数据)

用法:
    from legacy.data_platform.industry_crawlers.semi import fetch_semi_data
    data = fetch_semi_data()
"""

from __future__ import annotations
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("v57.data.industry.semi")

try:
    from core.models import DataPoint
except ImportError:
    from dataclasses import dataclass, field

    @dataclass
    class DataPoint:
        name: str = ""
        value: Any = None
        unit: str = ""
        source: str = ""
        source_level: str = ""
        confidence: str = "medium"
        is_estimate: bool = False
        fiscal_year: int | None = None
        note: str = ""


_HAS_CRAWL4AI = False
try:
    from crawl4ai import AsyncWebCrawler

    _HAS_CRAWL4AI = True
except ImportError:
    logger.warning("crawl4ai not installed, Semi data unavailable")


def fetch_semi_data() -> list[DataPoint]:
    if not _HAS_CRAWL4AI:
        return _mock_semi_data()
    try:
        import asyncio

        return asyncio.run(_fetch_semi_async())
    except Exception as e:
        logger.error("Semi data fetch failed: %s", e)
        return _mock_semi_data()


async def _fetch_semi_async() -> list[DataPoint]:
    points = []
    sources = [
        "https://www.wsts.org/",  # WSTS
        "https://www.semi.org/",  # SEMI
    ]
    async with AsyncWebCrawler() as crawler:
        for url in sources:
            try:
                result = await crawler.arun(url=url, bypass_cache=True)
                if result.success:
                    text = (
                        result.markdown.raw_markdown
                        if hasattr(result.markdown, "raw_markdown")
                        else str(result.markdown)
                    )
                    parsed = _parse_semi_page(text)
                    points.extend(parsed)
            except Exception as e:
                logger.debug("Semi crawl failed for %s: %s", url, e)
    if not points:
        return _mock_semi_data()
    return points


def _parse_semi_page(text: str) -> list[DataPoint]:
    points = []
    patterns = {
        "semi_global_sales": [(r"全球[^。]*?(\d+\.?\d*)\s*亿[美](?:元|刀)"), (r"全球[^。]*?销售额[^。]*?(\d+\.?\d*)")],
        "semi_china_sales": [(r"中国[^。]*?(\d+\.?\d*)\s*亿[美](?:元|刀)"), (r"中国[^。]*?销售额[^。]*?(\d+\.?\d*)")],
        "semi_capex": [(r"资本[^。]*?(\d+\.?\d*)\s*亿[美](?:元|刀)"), (r"支出[^。]*?(\d+\.?\d*)\s*亿[美](?:元|刀)")],
        "semi_capacity_util": [(r"产能利用率[^。]*?(\d+\.?\d*)%")],
    }
    units = {
        "semi_global_sales": "亿美元",
        "semi_china_sales": "亿美元",
        "semi_capex": "亿美元",
        "semi_capacity_util": "%",
    }
    for name, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text)
            if m:
                try:
                    points.append(
                        DataPoint(
                            name=name,
                            value=float(m.group(1)),
                            unit=units.get(name, ""),
                            source="crawl4ai/semi",
                            source_level="L2_provider",
                            confidence="medium",
                        )
                    )
                except ValueError:
                    pass
                break
    return points


def _mock_semi_data() -> list[DataPoint]:
    return [
        DataPoint(
            name="semi_global_sales",
            value=6280.0,
            unit="亿美元",
            source="mock/WSTS",
            source_level="L3_estimate",
            confidence="low",
            note="模拟数据(爬虫不可用)",
        ),
        DataPoint(
            name="semi_china_sales",
            value=1850.0,
            unit="亿美元",
            source="mock/WSTS",
            source_level="L3_estimate",
            confidence="low",
        ),
        DataPoint(
            name="semi_capex",
            value=1680.0,
            unit="亿美元",
            source="mock/SEMI",
            source_level="L3_estimate",
            confidence="low",
        ),
        DataPoint(
            name="semi_capacity_util",
            value=82.5,
            unit="%",
            source="mock/SEMI",
            source_level="L3_estimate",
            confidence="low",
        ),
    ]
