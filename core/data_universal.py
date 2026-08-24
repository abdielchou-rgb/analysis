"""万能数据采集器 — 零依赖，只靠requests

当akshare/tavily/yfinance都不可用时作为备用。
从东方财富、新浪财经等公开API直接抓取。
"""

import re, json, logging, time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.universal")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# 尝试导入akshare(如果可用)
try:
    import akshare as _ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

try:
    import yfinance as _yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
except ImportError:
    HAS_REQUESTS = False


def fetch_stock_price(code: str) -> dict:
    """获取A股实时行情（东方财富API）"""
    if not HAS_REQUESTS:
        return {"error": "requests not installed"}
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid=1.{code}&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f115,f170"
        r = requests.get(url, timeout=5, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200:
            d = r.json().get("data", {})
            return {
                "price": d.get("f43", 0) / 100,
                "high": d.get("f44", 0) / 100,
                "low": d.get("f45", 0) / 100,
                "open": d.get("f46", 0) / 100,
                "volume": d.get("f47", 0),
                "amount": d.get("f48", 0),
                "market_cap": d.get("f50", 0),
                "code": code,
            }
    except Exception as e:
        logger.debug("fetch_stock_price: %s", e)
    # Fallback: Sina finance
    try:
        r2 = requests.get(f"https://hq.sinajs.cn/list=sh{code}", timeout=5,
            headers={"Referer":"https://finance.sina.com.cn"})
        if r2.status_code == 200:
            parts = r2.text.split(",")
            if len(parts) > 3:
                return {
                    "price": float(parts[3]) if parts[3] else 0,
                    "open": float(parts[1]) if parts[1] else 0,
                    "high": float(parts[4]) if parts[4] else 0,
                    "low": float(parts[5]) if parts[5] else 0,
                    "volume": int(float(parts[8])) if parts[8] else 0,
                    "code": code,
                }
    except Exception:
        pass
    return {"error": "failed"}


def fetch_financial_summary(code: str) -> dict:
    """获取财务数据摘要（新浪财经API）"""
    if not HAS_REQUESTS:
        return {"error": "requests not installed"}
    try:
        url = f"https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_LICO_FN_CPD&columns=REPORT_DATE,SECUCODE,SECURITY_NAME_ABBR,TOTAL_OPERATE_INCOME,PARENT_NETPROFIT&filter=(SECUCODE%3D%22{code}.SH%22)&pageNumber=1&pageSize=3&sortTypes=-1&sortColumns=REPORT_DATE&source=WEB"
        r = requests.get(url, timeout=5, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200 and r.text.strip() and r.text.strip() != 'null':
            data = json.loads(r.text)
            # 提取最近3年
            result = {"revenue": {}, "net_profit": {}}
            for item in data[-3:] if len(data) >= 3 else data:
                year = str(item.get("report_date", ""))[:4]
                if year:
                    result["revenue"][year] = item.get("operate_income", 0) / 1e8
                    result["net_profit"][year] = item.get("net_profit", 0) / 1e8
            if result["revenue"]:
                return result
    except Exception as e:
        logger.debug("fetch_financial_summary: %s", e)
    # Fallback: Sina finance
    try:
        r2 = requests.get(f"https://hq.sinajs.cn/list=sh{code}", timeout=5,
            headers={"Referer":"https://finance.sina.com.cn"})
        if r2.status_code == 200:
            parts = r2.text.split(",")
            if len(parts) > 3:
                return {
                    "price": float(parts[3]) if parts[3] else 0,
                    "open": float(parts[1]) if parts[1] else 0,
                    "high": float(parts[4]) if parts[4] else 0,
                    "low": float(parts[5]) if parts[5] else 0,
                    "volume": int(float(parts[8])) if parts[8] else 0,
                    "code": code,
                }
    except Exception:
        pass
    return {"error": "failed"}


def fetch_industry(code: str) -> str:
    """获取行业分类"""
    if not HAS_REQUESTS:
        return ""
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid=1.{code}&fields=f57,f58"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            d = r.json().get("data", {})
            return f"{d.get('f57','')} {d.get('f58','')}"
    except Exception:
        pass
    return ""


def collect_akshare(code: str) -> dict:
    """akshare引擎(如果可用)"""
    if not HAS_AKSHARE:
        return {}
    try:
        fin = _ak.stock_financial_abstract_ths(symbol=code, indicator='按年度')
        if fin is not None and len(fin) > 0:
            data = fin.to_dict(orient='records') if hasattr(fin, 'to_dict') else str(fin)[:2000]
            return {'akshare_financials': data[:2000]}
    except Exception:
        pass
    return {}

def collect_yfinance(code: str) -> dict:
    """yfinance引擎(如果可用)"""
    if not HAS_YFINANCE:
        return {}
    try:
        tk = f"{code}.SS" if code.startswith(('6','9')) else f"{code}.SZ"
        info = _yf.Ticker(tk).info or {}
        return {k: info[k] for k in ['marketCap','trailingPE','returnOnEquity','sector','industry'] if k in info}
    except Exception:
        pass
    return {}

def collect_universal(asset: str) -> dict:
    """万能采集入口 — 识别股票代码并采集"""
    result = {"source": "universal", "status": "ok"}
    code_match = re.search(r"(\d{6})", asset)
    if not code_match:
        return {"source": "universal", "status": "no_code", "error": "no stock code found"}
    code = code_match.group(1)
    
    # 引擎0: akshare(如果可用) — 最精确的结构化数据
    ak_data = collect_akshare(code)
    if ak_data:
        result.update(ak_data)
    
    # 引擎0.5: yfinance(如果可用) — 国际数据覆盖
    yf_data = collect_yfinance(code)
    if yf_data:
        result['yfinance'] = yf_data
    
    # 实时行情
    price_data = fetch_stock_price(code)
    if "error" not in price_data:
        result["price"] = price_data
    
    # 财务摘要
    fin_data = fetch_financial_summary(code)
    if "error" not in fin_data:
        result["financials"] = fin_data
    
    # 行业
    industry = fetch_industry(code)
    if industry:
        result["industry"] = industry
    
    return result
