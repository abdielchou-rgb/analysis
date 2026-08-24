"""pv.py — 光伏行业数据管线

数据源: 硅业分会(硅料/硅片价格), PVInfolink(电池/组件价格), CPIA(产量/产能)

用法:
    from data.industry_crawlers.pv import fetch_pv_data
    data = fetch_pv_data()  # 返回 DataPoint[]
"""

from __future__ import annotations
import logging
from typing import Any, Optional

logger = logging.getLogger("v57.data.industry.pv")

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
    logger.warning("crawl4ai not installed, PV industry data unavailable")


def fetch_pv_data() -> list[DataPoint]:
    """获取光伏产业链数据：硅料/硅片/电池/组件价格 + 产量+产能"""
    if not _HAS_CRAWL4AI:
        return _mock_pv_data()
    try:
        import asyncio
        return asyncio.run(_fetch_pv_async())
    except Exception as e:
        logger.error("PV data fetch failed: %s", e)
        return _mock_pv_data()


async def _fetch_pv_async() -> list[DataPoint]:
    points = []
    sources = [
        "https://www.sienergy.cn/",  # 硅业分会
        "https://www.pvinfolink.com/",  # PVInfolink
    ]
    async with AsyncWebCrawler() as crawler:
        for url in sources:
            try:
                result = await crawler.arun(url=url, bypass_cache=True)
                if result.success:
                    text = result.markdown.raw_markdown if hasattr(result.markdown, "raw_markdown") else str(result.markdown)
                    parsed = _parse_pv_page(text)
                    points.extend(parsed)
            except Exception as e:
                logger.debug("PV crawl failed for %s: %s", url, e)
    if not points:
        return _mock_pv_data()
    return points


def _parse_pv_page(text: str) -> list[DataPoint]:
    import re
    points = []
    patterns = {
        "polysilicon_price": [(r"多晶硅[^。]*?(\d+\.?\d*)"), (r"硅料[^。]*?(\d+\.?\d*)")],
        "wafer_price": [(r"硅片[^。]*?(\d+\.?\d*)")],
        "cell_price": [(r"电池片[^。]*?(\d+\.?\d*)"), (r"电池[^。]*?(\d+\.?\d*)")],
        "module_price": [(r"组件[^。]*?(\d+\.?\d*)")],
    }
    units = {"polysilicon_price": "元/kg", "wafer_price": "元/片", "cell_price": "元/W", "module_price": "元/W"}
    for name, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text)
            if m:
                try:
                    points.append(DataPoint(name=name, value=float(m.group(1)), unit=units.get(name, ""),
                                            source="crawl4ai/pv", source_level="L2_provider", confidence="medium"))
                except ValueError:
                    pass
                break
    return points


def _mock_pv_data() -> list[DataPoint]:
    return [
        DataPoint(name="polysilicon_price", value=42.5, unit="元/kg", source="mock/硅业分会", source_level="L3_estimate", confidence="low", note="模拟数据(爬虫不可用)"),
        DataPoint(name="wafer_price", value=1.65, unit="元/片", source="mock/硅业分会", source_level="L3_estimate", confidence="low"),
        DataPoint(name="cell_price", value=0.78, unit="元/W", source="mock/PVInfolink", source_level="L3_estimate", confidence="low"),
        DataPoint(name="module_price", value=0.92, unit="元/W", source="mock/PVInfolink", source_level="L3_estimate", confidence="low"),
        DataPoint(name="pv_installation_2026e", value=280.0, unit="GW", source="mock/CPIA", source_level="L3_estimate", confidence="low"),
    ]
