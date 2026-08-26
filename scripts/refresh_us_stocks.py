# -*- coding: utf-8 -*-
"""刷新 us_stocks.db 300 只美股财务（stockanalysis.com），yfinance 限流时的替代源"""

import re
import sqlite3
import sys
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
DB_PATH = r"D:\Claude\projects\2hao-analyst\data\us_stocks.db"
AS_OF = "2026-08-25"  # 美股 8/25 收盘后（Marvis 定时刷新）


def fetch_quote(ticker: str):
    url = f"https://stockanalysis.com/stocks/{ticker}/"
    try:
        # 429 限流重试：0.5 -> 1 -> 2 -> 4 -> 8s
        r = None
        for attempt in range(6):
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 200:
                break
            if r.status_code == 429:
                time.sleep(1.5 * (2**attempt))
                continue
            return None
        if r is None or r.status_code != 200:
            return None
        txt = r.text

        # marketCap/peRatio 形如 "marketCap":"4.54T" 或 "marketCap":"4.54T",
        def num(key):
            m = re.search(key + r'[:"]+"?([\d,\.]+)([TBM]?)"', txt)
            if not m:
                return None
            v = float(m.group(1).replace(",", ""))
            u = m.group(2)
            if u == "T":
                v *= 1e12
            elif u == "B":
                v *= 1e9
            elif u == "M":
                v *= 1e6
            return v

        mc = num(r"marketCap")
        pe = num(r"peRatio")
        rev = num(r"totalRevenue")
        ni = num(r"netIncome")
        if mc is not None:
            mc = mc / 1e6  # 存 M 单位（与现库一致）
        if rev is not None:
            rev = rev / 1e6
        if ni is not None:
            ni = ni / 1e6
        return {"mc": mc, "pe": pe, "rev": rev, "ni": ni}
    except Exception:
        return None


def main():
    con = sqlite3.connect(DB_PATH)
    # 只处理 as_of 旧于目标日的行（幂等增量）
    tickers = [
        t[0] for t in con.execute("SELECT ticker FROM us_stocks WHERE as_of < ? ORDER BY ticker", (AS_OF,)).fetchall()
    ]
    # --limit 分批（防止单次超时）
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
        tickers = tickers[:limit]
    print(f"待刷新 {len(tickers)} 只，开始抓取...")
    results = {}
    fails = []
    # 串行执行 + 内置重试，避免 429 限流
    for i, t in enumerate(tickers, 1):
        q = fetch_quote(t)
        if q and q["mc"] is not None:
            results[t] = q
        else:
            fails.append(t)
        if i % 50 == 0:
            print(f"  进度 {i}/{len(tickers)}")
        time.sleep(0.8)
    print(f"成功 {len(results)}/{len(tickers)}, 失败 {len(fails)}")
    if fails:
        print("失败清单:", fails[:30])

    # 写入（幂等 INSERT OR REPLACE）
    now = AS_OF
    updated = 0
    for t, q in results.items():
        cur = con.execute(
            "UPDATE us_stocks SET as_of=?, revenue=COALESCE(?, revenue), net_profit=COALESCE(?, net_profit), "
            "market_cap=COALESCE(?, market_cap), pe_ttm=COALESCE(?, pe_ttm), source=? WHERE ticker=?",
            (now, q["rev"], q["ni"], q["mc"], q["pe"], f"stockanalysis.com (Marvis refresh {now})", t),
        )
        if cur.rowcount:
            updated += 1
    con.commit()
    print("已更新 as_of 行数:", updated)
    print("最新 as_of:", con.execute("SELECT MAX(as_of) FROM us_stocks").fetchone()[0])
    con.close()


if __name__ == "__main__":
    main()
