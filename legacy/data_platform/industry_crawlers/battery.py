"""battery.py — 锂电池行业数据管线

数据源: 高工锂电(价格/装机量), 中国化学与物理电源协会(产量/库存)

用法:
    from legacy.data_platform.industry_crawlers.battery import fetch_battery_data
    data = fetch_battery_data()
"""

from __future__ import annotations
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("v57.data.industry.battery")

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
    logger.warning("crawl4ai not installed, Battery data unavailable")


def fetch_battery_data() -> list[DataPoint]:
    if not _HAS_CRAWL4AI:
        return _mock_battery_data()
    try:
        import asyncio

        return asyncio.run(_fetch_battery_async())
    except Exception as e:
        logger.error("Battery data fetch failed: %s", e)
        return _mock_battery_data()


async def _fetch_battery_async() -> list[DataPoint]:
    points = []
    async with AsyncWebCrawler() as crawler:
        urls = ["https://www.gg-lb.com/", "https://www.ciaps.org.cn/"]
        for url in urls:
            try:
                result = await crawler.arun(url=url, bypass_cache=True)
                if result.success:
                    text = (
                        result.markdown.raw_markdown
                        if hasattr(result.markdown, "raw_markdown")
                        else str(result.markdown)
                    )
                    parsed = _parse_battery_page(text)
                    points.extend(parsed)
            except Exception as e:
                logger.debug("Battery crawl failed for %s: %s", url, e)
    if not points:
        return _mock_battery_data()
    return points


def _parse_battery_page(text: str) -> list[DataPoint]:
    points = []
    patterns = {
        "battery_carbonate_price": [(r"碳酸锂[^。]*?(\d+\.?\d*)"), (r"电池级碳酸锂[^。]*?(\d+\.?\d*)")],
        "battery_installation": [(r"装机[^。]*?(\d+\.?\d*)\s*GWh"), (r"装机[^。]*?(\d+\.?\d*)\s*亿只")],
        "battery_production": [(r"产量[^。]*?(\d+\.?\d*)\s*GWh")],
        "battery_utilization": [(r"开工[^。]*?(\d+\.?\d*)%"), (r"产能利用率[^。]*?(\d+\.?\d*)%")],
    }
    units = {
        "battery_carbonate_price": "万元/吨",
        "battery_installation": "GWh",
        "battery_production": "GWh",
        "battery_utilization": "%",
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
                            source="crawl4ai/battery",
                            source_level="L2_provider",
                            confidence="medium",
                        )
                    )
                except ValueError:
                    pass
                break
    return points


def _mock_battery_data() -> list[DataPoint]:
    return [
        DataPoint(
            name="battery_carbonate_price",
            value=10.5,
            unit="万元/吨",
            source="mock/高工锂电",
            source_level="L3_estimate",
            confidence="low",
            note="模拟数据(爬虫不可用)",
        ),
        DataPoint(
            name="battery_installation",
            value=38.2,
            unit="GWh",
            source="mock/高工锂电",
            source_level="L3_estimate",
            confidence="low",
        ),
        DataPoint(
            name="battery_production",
            value=42.0,
            unit="GWh",
            source="mock/高工锂电",
            source_level="L3_estimate",
            confidence="low",
        ),
        DataPoint(
            name="battery_utilization",
            value=65.8,
            unit="%",
            source="mock/GGII",
            source_level="L3_estimate",
            confidence="low",
        ),
    ]
