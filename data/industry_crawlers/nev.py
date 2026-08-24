"""nev.py — 新能源车行业数据管线

数据源: 乘联会(月度销量/渗透率), 中国汽车工业协会(产量/出口)

用法:
    from data.industry_crawlers.nev import fetch_nev_data
    data = fetch_nev_data()
"""

from __future__ import annotations
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("v57.data.industry.nev")

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
    logger.warning("crawl4ai not installed, NEV data unavailable")


def fetch_nev_data() -> list[DataPoint]:
    if not _HAS_CRAWL4AI:
        return _mock_nev_data()
    try:
        import asyncio
        return asyncio.run(_fetch_nev_async())
    except Exception as e:
        logger.error("NEV data fetch failed: %s", e)
        return _mock_nev_data()


async def _fetch_nev_async() -> list[DataPoint]:
    points = []
    sources = [
        "https://www.cpcaauto.com/",  # 乘联会
        "http://www.caam.org.cn/",  # 中汽协
    ]
    async with AsyncWebCrawler() as crawler:
        for url in sources:
            try:
                result = await crawler.arun(url=url, bypass_cache=True)
                if result.success:
                    text = result.markdown.raw_markdown if hasattr(result.markdown, "raw_markdown") else str(result.markdown)
                    parsed = _parse_nev_page(text)
                    points.extend(parsed)
            except Exception as e:
                logger.debug("NEV crawl failed for %s: %s", url, e)
    if not points:
        return _mock_nev_data()
    return points


def _parse_nev_page(text: str) -> list[DataPoint]:
    points = []
    patterns = {
        "nev_monthly_sales": [(r"新能源[^。]*?(\d+\.?\d*)\s*万辆"), (r"新能源[^。]*?(\d+\.?\d*)\s*台")],
        "nev_penetration_rate": [(r"渗透率[^。]*?(\d+\.?\d*)%"), (r"新能源渗透率[^。]*?(\d+\.?\d*)")],
        "nev_monthly_production": [(r"产量[^。]*?(\d+\.?\d*)\s*万辆")],
        "nev_export": [(r"出口[^。]*?(\d+\.?\d*)\s*万辆"), (r"出口[^。]*?(\d+\.?\d*)\s*台")],
    }
    units = {"nev_monthly_sales": "万辆", "nev_penetration_rate": "%", "nev_monthly_production": "万辆", "nev_export": "万辆"}
    for name, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text)
            if m:
                try:
                    points.append(DataPoint(name=name, value=float(m.group(1)), unit=units.get(name, ""),
                                            source="crawl4ai/nev", source_level="L2_provider", confidence="medium"))
                except ValueError:
                    pass
                break
    return points


def _mock_nev_data() -> list[DataPoint]:
    return [
        DataPoint(name="nev_monthly_sales", value=85.6, unit="万辆", source="mock/乘联会", source_level="L3_estimate", confidence="low", note="模拟数据(爬虫不可用)"),
        DataPoint(name="nev_penetration_rate", value=52.3, unit="%", source="mock/乘联会", source_level="L3_estimate", confidence="low"),
        DataPoint(name="nev_monthly_production", value=88.2, unit="万辆", source="mock/中汽协", source_level="L3_estimate", confidence="low"),
        DataPoint(name="nev_export", value=18.5, unit="万辆", source="mock/中汽协", source_level="L3_estimate", confidence="low"),
    ]
