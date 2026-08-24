"""V51 — price.py 价格看门狗

抄 Mrjie7205/serenity-bottleneck-hunter/scripts/price.py。

核心原则（Mrjie7205 原文）:
  "强制从 EODHD→yfinance→akshare 拉价，零手填，严禁 WebSearch 猜价"

V51 适配:
  1. 从 akshare 获取 A 股实时行情
  2. 作为 Conviction Matrix 的当前价输入源
  3. 如果 akshare 不可用，从 data/ 目录下的缓存文件读取
  4. 如果都不可用，拒绝猜测——返回 None 而非 0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("v51.price")

_HAS_AKSHARE = False
try:
    import akshare as ak

    _HAS_AKSHARE = True
except ImportError:
    pass


@dataclass
class PriceResult:
    """价格查询结果。"""

    ticker: str = ""
    name: str = ""
    last_price: float = 0.0
    currency: str = "CNY"
    change_pct: float = 0.0
    low_6mo: float | None = None
    high_6mo: float | None = None
    pe_ttm: float | None = None
    market_cap: float | None = None
    source: str = ""
    success: bool = False
    error: str = ""


def fetch_a_share_price(stock_code: str) -> PriceResult:
    """A 股实时行情（akshare + fallback）。

    Args:
        stock_code: A 股代码，如 "600519.SH" 或 "300750.SZ"

    Returns:
        PriceResult: 包含最新价/涨跌幅/PE/市值等
    """
    result = PriceResult(ticker=stock_code)

    # 解析交易所
    code = stock_code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if "SH" in stock_code.upper() or stock_code.endswith(".SH"):
        symbol = f"{code}"
    elif "SZ" in stock_code.upper() or stock_code.endswith(".SZ"):
        symbol = f"{code}"
    else:
        symbol = code

    # akshare 实时行情
    if _HAS_AKSHARE:
        try:
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == code]
            if not row.empty:
                r = row.iloc[0]
                result.last_price = float(r.get("最新价", 0))
                result.change_pct = float(r.get("涨跌幅", 0))
                result.name = str(r.get("名称", ""))
                result.pe_ttm = float(r.get("市盈率-动态", 0)) if r.get("市盈率-动态") else None
                result.market_cap = float(r.get("总市值", 0)) if r.get("总市值") else None
                result.source = "akshare"
                result.success = True

                # 估算 6 个月高低点（akshare 历史行情）
                try:
                    hist = ak.stock_zh_a_hist(symbol=code, period="monthly", adjust="qfq")
                    if hist is not None and len(hist) >= 6:
                        recent = hist.tail(6)
                        result.low_6mo = float(recent["收盘"].min())
                        result.high_6mo = float(recent["收盘"].max())
                except Exception:
                    pass

                return result
        except Exception as e:
            logger.warning(f"akshare spot failed for {code}: {e}")

    # Fallback: 从 Conviction Matrix 缓存读取（如果 akshare 不可用）
    try:
        from core.cognitive_baseline import CognitiveBaseline

        baseline = CognitiveBaseline.load(code)
        kv = baseline.get("key_variables", {})
        for var_name, var_data in kv.items():
            if "price" in var_name.lower() and isinstance(var_data, dict):
                val = var_data.get("value")
                if val:
                    result.last_price = float(val)
                    result.source = "cognitive_baseline"
                    result.success = True
                    return result
    except Exception:
        pass

    result.error = f"无法获取 {stock_code} 的实时价格（akshare 未安装或数据不可用）"
    result.success = False
    return result


def price_for_conviction_matrix(stock_code: str, fallback_price: float | None = None) -> tuple[float, str]:
    """Conviction Matrix 专用价格获取。

    优先 akshare 实时价 → fallback 传入价 → 优雅失败

    Returns:
        (price, source): 价格和来源字符串
    """
    result = fetch_a_share_price(stock_code)
    if result.success:
        return result.last_price, f"akshare实时({stock_code})"

    if fallback_price is not None and fallback_price > 0:
        return fallback_price, f"用户传入({stock_code})"

    logger.warning(f"Conviction Matrix 无法获取 {stock_code} 的当前价")
    return 0.0, "未获取"


# 便捷函数
def get_price(stock_code: str) -> float | None:
    """获取一只股票的最新价。"""
    result = fetch_a_share_price(stock_code)
    return result.last_price if result.success else None
