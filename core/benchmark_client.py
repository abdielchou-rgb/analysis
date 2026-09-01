"""S1-2: 基准指数净值客户端

复用 verify_predictions.py 的 yfinance 逻辑，但抽象为可复用模块。
支持沪深300/中证500/中证1000，返回净值序列供预测窗口对齐。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

logger = logging.getLogger("benchmark_client")

# 指数代码映射
INDEX_CODES: dict[str, str] = {
    "hs300": "000300.SS",
    "zz500": "000905.SS",
    "zz1000": "000852.SS",
    "szzs": "399001.SZ",   # 深证综指
    "shzs": "000001.SS",   # 上证综指
}


def get_index_nav(index_code: str, date: str) -> float | None:
    """获取指定指数在指定日期的收盘净值。

    Args:
        index_code: 指数代码（如 'hs300', 'zz500' 或 yfinance ticker '000300.SS'）
        date: 日期字符串 YYYY-MM-DD
    Returns:
        净值（收盘价），获取失败返回 None
    """
    import yfinance as yf

    ticker = INDEX_CODES.get(index_code, index_code)
    try:
        dt = datetime.fromisoformat(date)
        start = (dt - timedelta(days=7)).strftime("%Y-%m-%d")
        end = (dt + timedelta(days=2)).strftime("%Y-%m-%d")
        df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
        if df is not None and not df.empty and "Close" in df.columns:
            df = df.sort_index()
            available = df.index[df.index <= pd.Timestamp(dt)]
            if len(available) > 0:
                return float(df.loc[available[-1], "Close"])
    except Exception as e:
        logger.debug("获取 %s 在 %s 净值失败: %s", ticker, date, e)
    return None


def get_index_nav_series(index_code: str, start_date: str, end_date: str | None = None) -> dict[str, float]:
    """获取指数净值序列 {date_str: nav}，供预测窗口对齐。

    Args:
        index_code: 指数代码
        start_date: 起始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD（默认今天）
    Returns:
        {date_str: nav} 字典
    """
    import yfinance as yf

    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    ticker = INDEX_CODES.get(index_code, index_code)
    try:
        df = yf.Ticker(ticker).history(start=start_date, end=end_date, auto_adjust=True)
        if df is not None and not df.empty and "Close" in df.columns:
            df = df.sort_index()
            return {idx.strftime("%Y-%m-%d"): float(val) for idx, val in df["Close"].items()}
    except Exception as e:
        logger.debug("获取 %s 净值序列失败: %s", ticker, e)
    return {}


def compute_benchmark_return(index_code: str, start_date: str, end_date: str | None = None) -> float:
    """计算指数在指定区间的收益率。

    Args:
        index_code: 指数代码
        start_date: 起始日期
        end_date: 结束日期（默认今天）
    Returns:
        收益率（小数），失败返回 0.0
    """
    series = get_index_nav_series(index_code, start_date, end_date)
    if len(series) < 2:
        return 0.0
    dates = sorted(series.keys())
    start_nav = series[dates[0]]
    end_nav = series[dates[-1]]
    if start_nav <= 0:
        return 0.0
    return (end_nav - start_nav) / start_nav


def compute_alpha(actual_return: float, index_code: str, start_date: str, end_date: str | None = None) -> float:
    """计算超额收益 = 实际收益 - 基准收益。

    Args:
        actual_return: 实际收益率（小数）
        index_code: 基准指数代码
        start_date: 起始日期
        end_date: 结束日期
    Returns:
        Alpha（小数）
    """
    bench_return = compute_benchmark_return(index_code, start_date, end_date)
    return actual_return - bench_return


def get_best_benchmark_return(start_date: str, end_date: str | None = None) -> tuple[str, float]:
    """在沪深300/中证500中取更强的基准收益（兼容 verify_predictions 逻辑）。

    Returns:
        (benchmark_name, return) 元组
    """
    returns: dict[str, float] = {}
    for name in ("hs300", "zz500"):
        r = compute_benchmark_return(name, start_date, end_date)
        returns[name] = r

    if not returns:
        return ("hs300", 0.0)

    best = max(returns.items(), key=lambda x: x[1])
    return best
