# data_pipeline.py — Sequential data collection with per-source timeout
from __future__ import annotations
import os, re, time, logging

logger = logging.getLogger("2hao.data_pipeline")
_TIMEOUT = 15

class DataPipeline:
    def __init__(self):
        self._init_clients()
    def _init_clients(self):
        self._tavily = None; self._yfinance = None; self._akshare = None
        try:
            from tavily import TavilyClient
            k = os.environ.get("TAVILY_API_KEY","")
            if k: self._tavily = TavilyClient(api_key=k)
        except ImportError: pass
        try: import akshare as ak; self._akshare = ak
        except ImportError: pass
        try: import yfinance as yf; self._yfinance = yf
        except ImportError: pass
    def collect(self, asset: str, report_type: str = "industry_deep") -> dict:
        result = {}
        code = re.search(r"(\d{6})", asset)
        c = code.group(1) if code else ""
        if self._tavily:
            try: r = self._tavily.search(query=f"{asset} 分析 财务 行业", search_depth="basic", max_results=5, timeout=_TIMEOUT)
            except Exception: r = {"results":[]}
            if isinstance(r,dict) and r.get("results"): result["tavily"] = [x.get("content","")[:200] for x in r["results"][:5]]
        if self._akshare and c:
            try: fin = self._akshare.stock_financial_abstract_ths(symbol=c, indicator="按年度")
            except Exception: fin = None
            if fin is not None and len(fin) > 0:
                result["financials"] = str(fin.to_dict(orient="records") if hasattr(fin,"to_dict") else fin)[:2000]
        if self._yfinance and c:
            try:
                tk = f"{c}.SS" if c.startswith(("6","9")) else f"{c}.SZ"
                info = self._yfinance.Ticker(tk).info or {}
                result["yfinance"] = {k: info[k] for k in ["marketCap","trailingPE","returnOnEquity","sector","industry"] if k in info}
            except Exception: pass
        return result
