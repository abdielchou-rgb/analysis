# -*- coding: utf-8 -*-
"""Round5 F: 优先补齐 market_cap NULL 行"""

import re
import sqlite3
import sys
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch_quote(ticker):
    url = f"https://stockanalysis.com/stocks/{ticker}/"
    try:
        r = SESSION.get(url, timeout=25)
        if r.status_code != 200:
            return None
        text = r.text

        def num(key):
            m = re.search(key + r':"([\d,\.]+)([TBM]?)"', text)
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
        pb = num(r"pbRatio")
        if mc:
            mc = mc / 1e6
        return (mc, pe, pb)
    except Exception:
        return None


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 60
    conn = sqlite3.connect(r"D:\2hao-analyst\data\us_stocks.db")
    cur = conn.cursor()
    # 优先补 mc NULL
    rows = cur.execute("SELECT ticker FROM us_stocks WHERE market_cap IS NULL LIMIT ?", (limit,)).fetchall()
    if not rows:
        # 再补 pe NULL
        rows = cur.execute("SELECT ticker FROM us_stocks WHERE pe_ttm IS NULL LIMIT ?", (limit,)).fetchall()
    tickers = [t[0] for t in rows]
    print(f"本批 {len(tickers)} 只")
    ok = 0
    fails = []
    for t in tickers:
        q = fetch_quote(t)
        if q and q[0]:
            cur.execute("UPDATE us_stocks SET market_cap=?, pe_ttm=?, pb=? WHERE ticker=?", (q[0], q[1], q[2], t))
            ok += 1
        else:
            fails.append(t)
        time.sleep(1.5)
    conn.commit()
    mc_ok = cur.execute("SELECT COUNT(*) FROM us_stocks WHERE market_cap IS NOT NULL").fetchone()[0]
    pe_ok = cur.execute("SELECT COUNT(*) FROM us_stocks WHERE pe_ttm IS NOT NULL").fetchone()[0]
    conn.close()
    print(f"成功 {ok}/{len(tickers)}, mc: {mc_ok}/202, pe: {pe_ok}/202")
    if fails:
        print("失败:", fails)


if __name__ == "__main__":
    main()
