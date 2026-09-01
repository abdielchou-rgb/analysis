# Data Backends — 多数据源抽象层，akshare崩溃时自动切换
# 尝试顺序: akshare → yfinance → 计算估计 → 行业均值

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("2hao.data_backends")

# ── 可用性检测 ─────────────────────────────────────

_BACKENDS = {}

try:
    import akshare as ak  # noqa: F401  (dead-import debt)

    _BACKENDS["akshare"] = True
    logger.info("Backend: akshare available")
except ImportError:
    _BACKENDS["akshare"] = False
    logger.info("Backend: akshare unavailable")

try:
    import yfinance as yf  # noqa: F401  (dead-import debt)

    _BACKENDS["yfinance"] = True
    logger.info("Backend: yfinance available")
except ImportError:
    _BACKENDS["yfinance"] = False
    logger.info("Backend: yfinance unavailable")

try:
    import numpy as np  # noqa: F401  (dead-import debt)
    import pandas as pd  # noqa: F401  (availability probe)

    _BACKENDS["pandas"] = True
except ImportError:
    _BACKENDS["pandas"] = False


# ── 缓存层 ──────────────────────────────────────────

CACHE_DIR = Path(__file__).resolve().parent.parent / "output" / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB = CACHE_DIR / "data_cache.db"
CACHE_TTL_HOURS = 4  # 4小时缓存有效


def _init_cache():
    """初始化缓存数据库"""
    try:
        from core.sqlite_pool import get_connection

        conn = get_connection(str(CACHE_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                created_at TEXT,
                ttl_hours REAL DEFAULT 4
            )
        """)
        conn.commit()
        return True
    except Exception as e:
        logger.debug("Cache init: %s", e)
        return False


def cache_get(key: str) -> dict | None:
    """读取缓存"""
    try:
        from core.sqlite_pool import get_connection

        conn = get_connection(str(CACHE_DB), read_only=True)
        cur = conn.execute("SELECT value, created_at, ttl_hours FROM data_cache WHERE key = ?", (key,))
        row = cur.fetchone()
        if row:
            value, created, ttl = row
            created_dt = datetime.fromisoformat(created)
            if datetime.now() - created_dt < timedelta(hours=ttl):
                return json.loads(value)
            else:
                logger.debug("Cache expired: %s", key)
    except Exception as e:
        logger.debug("Cache read: %s", e)
    return None


def cache_set(key: str, value: dict, ttl: float = CACHE_TTL_HOURS):
    """写入缓存（单写者模式，WAL + 写锁）"""
    try:
        from core.sqlite_pool import write_execute

        write_execute(
            str(CACHE_DB),
            "INSERT OR REPLACE INTO data_cache (key, value, created_at, ttl_hours) VALUES (?, ?, ?, ?)",
            (key, json.dumps(value, default=str, ensure_ascii=False), datetime.now().isoformat(), ttl),
        )
    except Exception as e:
        logger.debug("Cache write: %s", e)


# ── 断路器 ──────────────────────────────────────────


class CircuitBreaker:
    """每数据源的断路器 — 连续失败N次后跳过"""

    def __init__(self, threshold: int = 3, cooldown_seconds: int = 300):
        self.threshold = threshold
        self.cooldown = cooldown_seconds
        self._failures: dict[str, int] = {}
        self._last_fail: dict[str, float] = {}

    def allow(self, source: str) -> bool:
        now = time.time()
        fails = self._failures.get(source, 0)
        last = self._last_fail.get(source, 0)
        if fails >= self.threshold:
            if now - last < self.cooldown:
                return False  # 熔断中
            else:
                self._failures[source] = 0  # 冷却后重置
        return True

    def fail(self, source: str):
        self._failures[source] = self._failures.get(source, 0) + 1
        self._last_fail[source] = time.time()

    def success(self, source: str):
        self._failures[source] = 0  # 成功后重置

    def status(self) -> dict:
        return {s: f"broken({self.cooldown}s)" if f >= self.threshold else "ok" for s, f in self._failures.items()}


_CIRCUIT = CircuitBreaker()


# ── 多后端查询引擎 ────────────────────────────────


def _query_local_qlib_price(code: str) -> dict | None:
    """优先查本地 Qlib bin（离线，秒级）。返回 {source, prices, dates} 或 None"""
    try:
        import numpy as np

        qlib_dir = Path(__file__).resolve().parent.parent / "data" / "qlib_bin"
        cal_path = qlib_dir / "calendars" / "day.txt"
        if not cal_path.exists():
            return None
        # 代码归一化: 600519 -> sh600519；兼容带市场后缀（300750.SZ / 600519.SH / 00700.HK）
        # 修复（2026-08-04 预测闭环审计）：旧逻辑不剥离 ".SZ/.SH" 后缀，导致
        # "300750.SZ".zfill(6)="300750.SZ" → 拼接成 "sz300750.SZ"，与 qlib 特征目录
        # "sz300750" 不匹配，_query_local_qlib_price 恒返回 None → 预测验证/目标价
        # 台账无法取价。先剥离后缀再补零前缀。
        c = re.sub(r"\.(SH|SZ|SS|BJ|HK|US)$", "", code.strip().upper())
        if not c.startswith(("SH", "SZ", "BJ")):
            c = c.zfill(6)
            c = ("sh" if c.startswith(("6", "9")) else "sz") + c
        else:
            c = c[:2].lower() + c[2:]
        feat_dir = qlib_dir / "features" / c
        if not feat_dir.exists():
            return None
        # close.day.bin 是 qlib 的**收益率指数**（起点=1.0，表示"投入1元到该日"的净值），
        # 不是绝对股价。消费方必须用**比值**计算收益（如 close[t]/close[as_of]-1），
        # 不能把它当股价与 current_price(元) 直接相减。
        # 注意：adjclose.day.bin 是**累计复权价**（含分红回补，长历史个股如格力/茅台
        # 会到数千上万），同样不是当前市价。两列都只适合算收益率，不适合取绝对价。
        close_path = feat_dir / "close.day.bin"
        if not close_path.exists():
            return None
        raw = close_path.read_bytes()
        arr = np.frombuffer(raw, dtype="<f4")
        if len(arr) < 2:
            return None
        start_idx = int(arr[0])
        closes = arr[1:]
        cal = cal_path.read_text(encoding="utf-8").splitlines()
        dates = [cal[start_idx + i] for i in range(len(closes)) if start_idx + i < len(cal)]
        # 取最近 60 个月末（月度采样）
        monthly = {}
        for d, px in zip(dates, closes):
            monthly[d[:7]] = float(px)
        keys = sorted(monthly.keys())[-60:]
        return {
            "source": "qlib_local",
            "prices": [monthly[k] for k in keys],
            "dates": [k for k in keys],
        }
    except Exception as e:
        logger.debug("qlib local price: %s", str(e)[:60])
        return None


def _query_local_financials(code: str) -> dict | None:
    """查本地财务层 SQLite（Baostock 预拉取）。返回 {source, data} 或 None"""
    try:
        db = Path(__file__).resolve().parent.parent / "data" / "financials.db"
        if not db.exists():
            return None
        from core.sqlite_pool import get_connection

        conn = get_connection(str(db), read_only=True)
        cur = conn.execute(
            "SELECT quarter, table_name, field, value FROM financials WHERE code=? ORDER BY quarter DESC LIMIT 60",
            (code[:6],),
        )
        rows = cur.fetchall()
        if not rows:
            return None
        return {"source": "qlib_financials", "data": rows}
    except Exception as e:
        logger.debug("qlib financials: %s", str(e)[:60])
        return None


def query_financial(code: str, max_retries: int = 2) -> dict:
    """多后端查询财务报表: 本地财务层 → Baostock → akshare → yfinance"""
    result = {}

    # 后端0: 本地财务层（离线，最优先）
    local = _query_local_financials(code)
    if local:
        return local

    # 后端0.5: Baostock（免费稳定）
    if _CIRCUIT.allow("baostock_fin"):
        try:
            import baostock as bs

            lg = bs.login()
            if lg.error_code == "0":
                bs_code = ("sh." if code[:6].startswith(("6", "9")) else "sz.") + code[:6]
                rs = bs.query_profit_data(code=bs_code, year="", quarter="")
                records = []
                while (rs.error_code == "0") and rs.next():
                    records.append(rs.get_row_data())
                bs.logout()
                if records:
                    result["source"] = "baostock"
                    result["data"] = records[-5:]  # 最近 5 期
                    _CIRCUIT.success("baostock_fin")
                    return result
        except Exception as e:
            logger.debug("baostock fin: %s", str(e)[:60])
        _CIRCUIT.fail("baostock_fin")

    # 后端1: akshare
    if _BACKENDS.get("akshare") and _CIRCUIT.allow("akshare_fin"):
        for attempt in range(max_retries):
            try:
                import akshare as ak

                fin = ak.stock_financial_abstract_ths(symbol=code[:6], indicator="按年度")
                if fin is not None and len(fin) > 0:
                    result["source"] = "akshare"
                    result["data"] = fin.to_dict(orient="records") if hasattr(fin, "to_dict") else str(fin)[:2000]
                    _CIRCUIT.success("akshare_fin")
                    return result
            except Exception as e:
                logger.warning("akshare fin fail (attempt %d/2): %s", attempt + 1, e[:60] if len(str(e)) > 60 else e)
                time.sleep(1 * (attempt + 1))
        _CIRCUIT.fail("akshare_fin")

    # 后端2: yfinance (修正ticker格式)
    if _BACKENDS.get("yfinance") and _CIRCUIT.allow("yfinance_fin"):
        try:
            import yfinance as yf

            ticker = _to_yfinance_ticker(code)
            if ticker:
                stock = yf.Ticker(ticker)
                info = stock.info or {}
                if info and info.get("marketCap"):
                    result["source"] = "yfinance"
                    result["yf_info"] = {
                        "market_cap": info.get("marketCap"),
                        "pe": info.get("trailingPE"),
                        "pb": info.get("priceToBook"),
                        "roe": info.get("returnOnEquity"),
                        "debt_to_equity": info.get("debtToEquity"),
                        "dividend_yield": info.get("dividendYield"),
                        "revenue": info.get("totalRevenue"),
                        "net_income": info.get("netIncomeToCommon"),
                        "sector": info.get("sector"),
                        "industry": info.get("industry"),
                    }
                    _CIRCUIT.success("yfinance_fin")
                    return result
        except Exception as e:
            logger.debug("yfinance: %s", e)
        _CIRCUIT.fail("yfinance_fin")

    return result  # 空字典 = 所有后端都失败


def query_price_history(code: str) -> dict:
    """多后端查询股价历史: 本地Qlib → akshare → yfinance"""
    result = {}

    # 后端0: 本地 Qlib（离线，最优先）
    local = _query_local_qlib_price(code)
    if local:
        return local

    # 后端1: akshare
    if _BACKENDS.get("akshare") and _CIRCUIT.allow("akshare_price"):
        try:
            import akshare as ak

            hist = ak.stock_zh_a_hist(symbol=code[:6], period="monthly", adjust="qfq", start_date="20200101")
            if hist is not None and len(hist) > 10:
                result["source"] = "akshare"
                result["prices"] = hist["收盘"].tolist()[:60]
                result["dates"] = hist["日期"].tolist()[:60] if "日期" in hist.columns else []
                _CIRCUIT.success("akshare_price")
                return result
        except Exception as e:
            logger.debug("akshare price: %s", str(e)[:60])
        _CIRCUIT.fail("akshare_price")

    # 后端2: yfinance
    if _BACKENDS.get("yfinance") and _CIRCUIT.allow("yfinance_price"):
        try:
            import yfinance as yf

            ticker = _to_yfinance_ticker(code)
            if ticker:
                hist = yf.download(ticker, period="5y", interval="1mo", progress=False)
                if hist is not None and len(hist) > 10:
                    result["source"] = "yfinance"
                    result["prices"] = hist["Close"].tolist() if "Close" in hist.columns else []
                    _CIRCUIT.success("yfinance_price")
                    return result
        except Exception as e:
            logger.debug("yfinance price: %s", str(e)[:60])
        _CIRCUIT.fail("yfinance_price")

    return result


def query_macro() -> dict:
    """多后端查询宏观数据"""
    result = {}

    if not _BACKENDS.get("akshare") or not _CIRCUIT.allow("akshare_macro"):
        return result

    try:
        import akshare as ak

        # PMI
        try:
            pmi = ak.index_pmi_man_cx()
            if pmi is not None and len(pmi) > 0:
                result["pmi"] = float(pmi.iloc[-1, 1]) if pmi.shape[1] > 1 else 50.0
        except ImportError:
            pass

        # 利率
        try:
            rate = ak.macro_bank_china_interest_rate()
            if rate is not None and len(rate) > 0:
                result["interest_rate"] = float(rate.iloc[-1, 1]) if rate.shape[1] > 1 else 3.0
        except ImportError:
            pass

        # CPI
        try:
            cpi = ak.macro_china_cpi_monthly()
            if cpi is not None and len(cpi) > 0:
                result["cpi"] = float(cpi.iloc[-1, 1]) if cpi.shape[1] > 1 else 0
        except ImportError:
            pass

        if result:
            _CIRCUIT.success("akshare_macro")
    except Exception as e:
        logger.debug("macro: %s", e)
        _CIRCUIT.fail("akshare_macro")

    return result


def _to_yfinance_ticker(code: str) -> str | None:
    """将股票代码转为yfinance格式（A股/港股/美股通用）。

    A股: 6x/9x→.SS, 0x/2x/3x→.SZ
    港股: 5位数字→.HK (如 00700→0700.HK)
    美股: 字母代码直接返回 (如 AAPL, MSFT)
    """
    code = code.strip()
    # 美股：字母开头直接返回
    if code and code[0].isalpha():
        return code.upper()
    # 港股：5位数字 (00700, 09988 等)
    clean = code.replace(".HK", "").replace(".hk", "")
    if clean.isdigit() and len(clean) == 5:
        return f"{clean}.HK"
    # A股：6位数字
    clean6 = code[:6]
    if clean6.isdigit() and len(clean6) == 6:
        if clean6.startswith(("6", "9")):
            return f"{clean6}.SS"
        elif clean6.startswith(("0", "2", "3")):
            return f"{clean6}.SZ"
    return None


def get_industry_avg(industry: str, metric: str) -> float | None:
    """行业均值数据库（内置）"""
    benchmarks = {
        "白酒": {"pe": 30, "roe": 20, "margin": 35, "growth": 15},
        "半导体": {"pe": 50, "roe": 10, "margin": 15, "growth": 25},
        "互联网": {"pe": 25, "roe": 15, "margin": 20, "growth": 18},
        "银行": {"pe": 6, "roe": 10, "margin": 35, "growth": 5},
        "医药": {"pe": 35, "roe": 12, "margin": 18, "growth": 15},
        "食品饮料": {"pe": 28, "roe": 18, "margin": 20, "growth": 12},
        "家电": {"pe": 15, "roe": 15, "margin": 12, "growth": 8},
        "汽车": {"pe": 20, "roe": 10, "margin": 8, "growth": 10},
        "化工": {"pe": 18, "roe": 10, "margin": 12, "growth": 8},
        "机械": {"pe": 22, "roe": 8, "margin": 10, "growth": 10},
        "电气设备": {"pe": 25, "roe": 10, "margin": 12, "growth": 15},
        "有色": {"pe": 20, "roe": 8, "margin": 8, "growth": 8},
        "军工": {"pe": 50, "roe": 5, "margin": 8, "growth": 12},
        "传媒": {"pe": 25, "roe": 8, "margin": 10, "growth": 10},
        "房地产": {"pe": 8, "roe": 8, "margin": 15, "growth": 3},
    }
    for key, vals in benchmarks.items():
        if key in industry:
            return vals.get(metric)
    return None


def circuit_status() -> dict:
    """返回断路器状态"""
    return _CIRCUIT.status()
