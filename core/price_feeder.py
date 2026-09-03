"""P0-1: Price feeder — real price backend for outcome resolution.

Fetches actual closing prices via akshare (A-shares) or yfinance (HK/US).
Returns None on failure — never fabricates prices.

Usage:
    from core.price_feeder import get_price
    price = get_price("宁德时代", "2026-06-01")
"""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("2hao.price_feeder")


def _is_a_share(asset: str) -> bool:
    """Detect A-share by name pattern."""
    # A-share codes: 6-digit numeric (600xxx, 000xxx, 300xxx, 688xxx)
    if re.match(r'^\d{6}$', asset):
        return True
    # Chinese company names (not ending in .HK)
    if re.search(r'[\u4e00-\u9fff]', asset) and '.HK' not in asset:
        return True
    return False


def _is_hk_share(asset: str) -> bool:
    """Detect HK share by .HK suffix or 5-digit code."""
    if '.HK' in asset:
        return True
    if re.match(r'^\d{5}$', asset):
        return True
    return False


def _normalize_date(date_str: str) -> str:
    """Normalize date to YYYY-MM-DD format."""
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def _fetch_akshare(asset: str, date: str) -> Optional[float]:
    """Fetch A-share closing price via akshare.

    Args:
        asset: Stock code (e.g., '300750') or name (e.g., '宁德时代')
        date: Date string YYYY-MM-DD

    Returns:
        Closing price or None
    """
    try:
        import akshare as ak

        # Normalize asset to code if it's a name
        code = asset
        if not re.match(r'^\d{6}$', asset):
            # Try to find code from name
            try:
                df = ak.stock_info_a_code_name()
                match = df[df['name'] == asset]
                if not match.empty:
                    code = match.iloc[0]['code']
                else:
                    logger.warning("[PRICE] Cannot find code for asset: %s", asset)
                    return None
            except Exception:
                logger.warning("[PRICE] Failed to lookup code for: %s", asset)
                return None

        # Fetch daily data
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=date.replace("-", ""),
            end_date=date.replace("-", ""),
            adjust="qfq",  # 前复权
        )

        if df.empty:
            logger.warning("[PRICE] No data for %s on %s", code, date)
            return None

        price = float(df.iloc[0]['收盘'])
        logger.info("[PRICE] akshare: %s @ %s = %.2f", code, date, price)
        return price

    except ImportError:
        logger.warning("[PRICE] akshare not installed")
        return None
    except Exception as e:
        logger.warning("[PRICE] akshare failed for %s@%s: %s", asset, date, str(e)[:100])
        return None


def _fetch_yfinance(asset: str, date: str) -> Optional[float]:
    """Fetch HK/US share closing price via yfinance.

    Args:
        asset: Ticker (e.g., '300750.HK', 'AAPL')
        date: Date string YYYY-MM-DD

    Returns:
        Closing price or None
    """
    try:
        import yfinance as yf

        # Normalize ticker
        ticker = asset
        if _is_hk_share(asset) and '.HK' not in asset:
            # 5-digit HK code → append .HK
            ticker = f"{asset}.HK"

        stock = yf.Ticker(ticker)
        hist = stock.history(start=date, end=date)

        if hist.empty:
            # Try adjacent dates (±3 days) for holiday/weekend
            dt = datetime.strptime(date, "%Y-%m-%d")
            for delta in [1, -1, 2, -2, 3, -3]:
                adj_date = (dt + timedelta(days=delta)).strftime("%Y-%m-%d")
                hist = stock.history(start=adj_date, end=adj_date)
                if not hist.empty:
                    break

        if hist.empty:
            logger.warning("[PRICE] yfinance: no data for %s near %s", ticker, date)
            return None

        price = float(hist.iloc[0]['Close'])
        logger.info("[PRICE] yfinance: %s @ %s = %.2f", ticker, date, price)
        return price

    except ImportError:
        logger.warning("[PRICE] yfinance not installed")
        return None
    except Exception as e:
        logger.warning("[PRICE] yfinance failed for %s@%s: %s", asset, date, str(e)[:100])
        return None


def get_price(
    asset: str,
    date: str,
    backend: str = "auto",
) -> Optional[float]:
    """Get real closing price for an asset on a date.

    Args:
        asset: Stock code/name (e.g., '300750', '宁德时代', '300750.HK', 'AAPL')
        date: Date string (YYYY-MM-DD, YYYYMMDD, etc.)
        backend: 'auto', 'akshare', 'yfinance', or 'mock'

    Returns:
        Closing price float, or None if unavailable.
        None means "data unavailable" — caller MUST NOT fabricate.
    """
    date = _normalize_date(date)

    if backend == "mock":
        logger.warning("[PRICE] Mock backend requested for %s@%s", asset, date)
        return None

    if backend in ("auto", "akshare"):
        if _is_a_share(asset):
            price = _fetch_akshare(asset, date)
            if price is not None:
                return price
            if backend == "akshare":
                return None

    if backend in ("auto", "yfinance"):
        if _is_hk_share(asset) or not _is_a_share(asset):
            price = _fetch_yfinance(asset, date)
            if price is not None:
                return price
            if backend == "yfinance":
                return None

    # Auto: try yfinance as fallback for anything
    if backend == "auto":
        price = _fetch_yfinance(asset, date)
        if price is not None:
            return price

    logger.info("[PRICE] No price available for %s@%s (backend=%s)", asset, date, backend)
    return None


def get_price_or_unverifiable(
    asset: str,
    date: str,
    backend: str = "auto",
) -> dict:
    """Get price with explicit unverifiable status.

    Returns:
        {price: float|None, status: "verified"|"unverifiable", detail: str}
    """
    price = get_price(asset, date, backend)

    if price is not None and price > 0:
        return {
            "price": price,
            "status": "verified",
            "detail": f"{asset}@{date}={price:.2f}",
        }
    else:
        return {
            "price": None,
            "status": "unverifiable",
            "detail": f"data_unavailable:{asset}@{date}",
        }
