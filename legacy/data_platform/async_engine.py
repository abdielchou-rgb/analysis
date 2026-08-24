"""V51 AsyncDataPipeline — parallel multi-source data fetch.

Inspired by FinAgents' asyncio.gather() approach.
Parallel fetch from EastMoney + Tencent K-line simultaneously.
"""

from __future__ import annotations
import asyncio, logging
from core.models import DataPoint

logger = logging.getLogger("v51.data.async_pipeline")

_HAS_HTTPX = False
try:
    import httpx

    _HAS_HTTPX = True
except ImportError:
    pass


async def _fetch_eastmoney(code: str, session=None) -> list[DataPoint]:
    """Fetch real-time quote from EastMoney."""
    m = "1." if code.startswith("6") else "0."
    url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids={m}{code}&fields=f2,f3,f12,f14,f20,f37,f45,f46,f48,f50"
    try:
        if _HAS_HTTPX:
            s = session or httpx.AsyncClient()
            r = await s.get(url, timeout=10)
            data = r.json()
        else:
            import requests

            s = requests.Session()
            s.headers.update({"User-Agent": "Mozilla/5.0"})
            r = s.get(url, timeout=10)
            data = r.json()
        diff = data.get("data", {}).get("diff", [{}])[0] if data.get("data") else {}
        pts = []
        for field, name, unit in [
            ("f2", "price", "yuan"),
            ("f3", "chg_pct", "%"),
            ("f20", "mcap", "yuan"),
            ("f37", "pe", "x"),
            ("f45", "revenue_ttm", "yuan"),
            ("f46", "profit_ttm", "yuan"),
            ("f48", "pb", "x"),
        ]:
            v = diff.get(field)
            if v is not None:
                pts.append(
                    DataPoint(
                        name=name, value=v, unit=unit, source="eastmoney", source_level="L1_filing", confidence="high"
                    )
                )
        return pts
    except Exception as e:
        logger.debug("eastmoney %s: %s", code, e)
        return []


async def _fetch_kline(code: str, session=None) -> list[DataPoint]:
    """Fetch YTD change from Tencent K-line."""
    p = "sh" if code.startswith("6") else "sz"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={p}{code},day,,,320,qfq"
    try:
        if _HAS_HTTPX:
            s = session or httpx.AsyncClient()
            r = await s.get(url, timeout=10)
            data = r.json()
        else:
            import requests

            r = requests.get(url, timeout=10)
            data = r.json()
        days = (
            data.get("data", {}).get(f"{p}{code}", {}).get("qfqday", [])
            or data.get("data", {}).get(f"{p}{code}", {}).get("day", [])
            or []
        )
        if len(days) > 5:
            cs = [float(x[2]) for x in days if len(x) >= 3]
            return [
                DataPoint(
                    name="ytd_chg_pct", value=round((cs[-1] - cs[0]) / cs[0] * 100, 2), unit="%", source="tencent_kline"
                )
            ]
        return []
    except Exception as e:
        logger.debug("kline %s: %s", code, e)
        return []


class AsyncDataPipeline:
    """Parallel data fetcher — inspired by FinAgents."""

    async def fetch(self, codes: list[str]) -> list[DataPoint]:
        """Parallel fetch for multiple stock codes."""
        if not codes:
            return []
        if _HAS_HTTPX:
            async with httpx.AsyncClient(timeout=15) as session:
                tasks = []
                for code in codes:
                    tasks.append(_fetch_eastmoney(code, session))
                    tasks.append(_fetch_kline(code, session))
                results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []
            for code in codes:
                results.append(await _fetch_eastmoney(code))
                results.append(await _fetch_kline(code))

        all_points = []
        for r in results:
            if isinstance(r, list):
                all_points.extend(r)
        return all_points

    def fetch_kline(self, code: str) -> list:
        """Sync fallback for kline."""
        try:
            from legacy.data_platform.engine import pipeline

            return pipeline.fetch_kline(code)
        except Exception:
            import asyncio

            return asyncio.run(_fetch_kline(code))


async_pipeline = AsyncDataPipeline()
