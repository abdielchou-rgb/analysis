"""V50+ T1 Data Engine — East Money based financial data connector"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from core.models import DataPoint

class EastMoneyConnector:
    """A-share financial data connector via East Money public API"""

    def __init__(self, cache_path: Optional[str] = None):
        self._session = None
        self.cache_path = cache_path or str(Path(__file__).resolve().parent.parent / "local_cache.json")
        self._local_cache: dict = self._load_cache()

    def _load_cache(self) -> dict:
        try:
            p = Path(self.cache_path)
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_cache(self):
        try:
            Path(self.cache_path).write_text(
                json.dumps(self._local_cache, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/",
            })
        return self._session

    def fetch_real_time(self, stock_code: str, market: str = "") -> dict:
        """Fetch real-time market data"""
        if not market:
            market = "SZ" if stock_code.startswith("0") or stock_code.startswith("3") else "SH"
        secid = "0." if market == "SZ" else "1."
        url = (f"https://push2.eastmoney.com/api/qt/ulist.np/get"
               f"?fltt=2&secids={secid}{stock_code}"
               f"&fields=f2,f3,f12,f14,f20,f25,f37,f45,f46,f48,f50,f62,f115,f168")
        try:
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            diff = data.get("data", {}).get("diff", [])
            if diff:
                d = diff[0]
                return {
                    "code": d.get("f12", stock_code),
                    "name": d.get("f14", ""),
                    "price": d.get("f2"),
                    "change_pct": d.get("f3"),
                    "market_cap": d.get("f20"),
                    "pe_ttm": d.get("f37"),
                    "total_revenue_ttm": d.get("f45"),
                    "profit_ttm": d.get("f46"),
                    "pb": d.get("f48"),
                    "total_assets": d.get("f50"),
                }
        except Exception as e:
            return {"error": str(e)}
        return {"error": "no data"}

    def fetch_data_points(self, stock_code: str, market: str = "") -> list[DataPoint]:
        """Return structured DataPoints for T1 KnowledgePackage"""
        raw = self.fetch_real_time(stock_code, market)
        if "error" in raw:
            return [DataPoint(name="data_error", value=raw["error"], source="east_money")]
        points = []
        fields = [
            ("price", raw.get("price"), "元", "high"),
            ("change_pct", raw.get("change_pct"), "%", "high"),
            ("market_cap", raw.get("market_cap"), "元", "high"),
            ("pe_ttm", raw.get("pe_ttm"), "倍", "high"),
            ("total_revenue_ttm", raw.get("total_revenue_ttm"), "元", "high"),
            ("profit_ttm", raw.get("profit_ttm"), "元", "high"),
            ("pb", raw.get("pb"), "倍", "high"),
            ("total_assets", raw.get("total_assets"), "元", "high"),
        ]
        for name, value, unit, conf in fields:
            if value is not None:
                points.append(DataPoint(
                    name=name, value=value, unit=unit, source="east_money",
                    source_level="L1_filing", confidence=conf,
                    is_estimate=False,
                ))
        # Update local cache
        name = raw.get("name", "")
        if name and stock_code not in self._local_cache:
            self._local_cache[stock_code] = {
                "name": name, "last_updated": datetime.now().isoformat(),
                "last_price": raw.get("price"),
            }
            self._save_cache()
        return points
