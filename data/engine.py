"""V50+ DataPipeline — multi-source, zero-API-key"""

from __future__ import annotations
from dataclasses import dataclass, field
from core.models import DataPoint

@dataclass
class DataQuery:
    type: str = "market"; assets: list[str] = field(default_factory=list); days: int = 30

@dataclass
class DataResponse:
    points: list[DataPoint] = field(default_factory=list)
    source: str = ""; confidence: str = "medium"; error: str = ""

import logging, time as _time
logger = logging.getLogger("v51.data.engine")

try: import requests as req; HAS_REQ = True
except ImportError: HAS_REQ = False


class EastMoneyEngine:
    name = "eastmoney"

    MAX_RETRIES = 2
    RETRY_BACKOFF = 1.5   # base seconds, exponential: 1.5 / 3.0

    def fetch(self, q):
        if not HAS_REQ: return DataResponse(error="no requests", source=self.name)
        try:
            s = req.Session()
            s.headers.update({"User-Agent":"Mozilla/5.0","Referer":"https://quote.eastmoney.com/"})
            pts = []
            for code in q.assets:
                m = "1." if code.startswith("6") else "0."
                url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids={m}{code}&fields=f2,f3,f12,f14,f20,f37,f45,f46,f48,f50"
                r = self._get_with_retry(s, url, code, timeout=10)
                if r is None:
                    continue
                try:
                    payload = r.json()
                except ValueError:
                    logger.warning("EastMoneyEngine invalid JSON for %s", code)
                    continue
                if not payload:
                    continue
                d = (payload.get("data") or {}).get("diff") or []
                d = d[0] if d else None
                if d:
                    for f,n,u in [("f2","price","yuan"),("f3","chg_pct","%"),("f20","mcap","yuan"),
                                  ("f37","pe","x"),("f45","revenue_ttm","yuan"),("f46","profit_ttm","yuan"),("f48","pb","x")]:
                        v = d.get(f)
                        if v: pts.append(DataPoint(name=n, value=v, unit=u, source="eastmoney", source_level="L1_filing", confidence="high"))
            if not pts:
                return DataResponse(error="no data from eastmoney", source=self.name)
            return DataResponse(points=pts, source=self.name)
        except Exception as e:
            logger.error("EastMoneyEngine.fetch failed: %s", e)
            return DataResponse(error=f"eastmoney error: {e}", source=self.name)

    def _get_with_retry(self, session, url, code, timeout=10):
        """HTTP GET with exponential backoff retry for transient errors.

        R44（2026-08-02 全量审计修复）：EastMoney push2 接口频繁 Connection aborted，
        单次请求无重试导致整个标的数据拉取失败。加入 2 次重试（指数退避 1.5s/3.0s），
        覆盖 ConnectionError / Timeout / OSError / ConnectionAbortedError 等瞬时故障。
        """
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                r = session.get(url, timeout=timeout)
                if r.status_code != 200 and attempt < self.MAX_RETRIES:
                    delay = self.RETRY_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "EastMoneyEngine %s HTTP %d (retry %d/%d, %.1fs backoff)",
                        code, r.status_code, attempt + 1, self.MAX_RETRIES, delay,
                    )
                    _time.sleep(delay)
                    continue
                return r
            except (req.ConnectionError, req.Timeout,
                    req.exceptions.ChunkedEncodingError,
                    OSError, ConnectionResetError, ConnectionAbortedError) as _exc:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "EastMoneyEngine %s %s (retry %d/%d, %.1fs backoff)",
                        code, type(_exc).__name__, attempt + 1, self.MAX_RETRIES, delay,
                    )
                    _time.sleep(delay)
                else:
                    logger.warning(
                        "EastMoneyEngine %s exhausted %d retries: %s",
                        code, self.MAX_RETRIES, _exc,
                    )
                    return None
        return None


class KLineEngine:
    name = "tencent_kline"

    def fetch_kline_raw(self, code: str) -> list:
        """Fetch raw K-line data from Tencent Finance.

        Returns list of [date, open, close, high, low, volume, ...] rows,
        or empty list on failure. Used by async engine and pipeline.
        """
        if not HAS_REQ:
            return []
        try:
            p = "sh" if code.startswith("6") else "sz"
            r = req.get(
                f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={p}{code},day,,,320,qfq",
                timeout=10,
            )
            d = r.json()
            return (d.get("data", {}).get(f"{p}{code}", {}).get("qfqday", [])
                    or d.get("data", {}).get(f"{p}{code}", {}).get("day", [])
                    or [])
        except Exception as e:
            logger.error("K-line raw fetch failed for %s: %s", code, e)
            raise

    def fetch(self, q):
        if not HAS_REQ: return DataResponse(error="no requests", source=self.name)
        pts = []
        for code in q.assets:
            try:
                p = "sh" if code.startswith("6") else "sz"
                r = req.get(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={p}{code},day,,,320,qfq", timeout=10)
                d = r.json()
                days = d.get("data",{}).get(f"{p}{code}",{}).get("qfqday",[]) or d.get("data",{}).get(f"{p}{code}",{}).get("day",[]) or []
                if len(days) > 5:
                    cs = [float(x[2]) for x in days if len(x) >= 3]
                    pts.append(DataPoint(name="ytd_chg_pct", value=round((cs[-1]-cs[0])/cs[0]*100,2), unit="%", source="tencent_kline"))
            except Exception as e:
                logger.error("KLineEngine.fetch failed for %s: %s", code, e)
                raise
        return DataResponse(points=pts, source=self.name)


class CacheEngine:
    name = "cache"
    CACHE = {"600519":[("name","Moutai")],"300750":[("name","CATL")]}
    def fetch(self, q):
        pts = []
        for code in q.assets:
            for k,v in self.CACHE.get(code, []):
                pts.append(DataPoint(name=k, value=v, source="cache"))
        return DataResponse(points=pts, source=self.name)


class DataPipeline:
    def __init__(self):
        self.engines = [EastMoneyEngine(), KLineEngine(), CacheEngine()]
        self._init_v56_engines()

    def _init_v56_engines(self):
        """Add V56 multi-dimensional data engines if available"""
        try:
            from data.yfinance_engine import YFinanceEngine
            self.engines.append(YFinanceEngine())
        except ImportError:
            pass
        try:
            from data.macro_engine import ChinaMacroEngine
            self.engines.append(ChinaMacroEngine())
        except ImportError:
            pass
        try:
            from data.cvc_engine import CVCEngine
            self.engines.append(CVCEngine())
        except ImportError:
            pass
        try:
            from data.news_engine import NewsEngine
            self.engines.append(NewsEngine())
        except ImportError:
            pass

    def fetch(self, q):
        errors = []
        for eng in self.engines:
            try:
                r = eng.fetch(q)
                if r.points:
                    return DataResponse(points=r.points, source=eng.name,
                                        confidence="high" if eng.name in ("eastmoney", "china_macro") else "medium")
            except Exception as e:
                errors.append(f"{eng.name}: {e}")
                continue
        return DataResponse(error=f"all failed ({'; '.join(errors[:3])})")

    def fetch_kline(self, code):
        if not HAS_REQ: return []
        try:
            p = "sh" if code.startswith("6") else "sz"
            r = req.get(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={p}{code},day,,,320,qfq", timeout=10)
            d = r.json()
            return d.get("data",{}).get(f"{p}{code}",{}).get("qfqday",[]) or d.get("data",{}).get(f"{p}{code}",{}).get("day",[]) or []
        except Exception as e:
            logger.error("fetch_kline failed for %s: %s", code, e)
            raise

pipeline = DataPipeline()
