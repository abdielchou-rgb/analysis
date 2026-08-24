# -*- coding: utf-8 -*-
"""Round5 F: 并发补抓美股市值/PE/PB"""
import requests, re, sqlite3, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def fetch_quote(ticker):
    url = f"https://stockanalysis.com/stocks/{ticker}/"
    try:
        r = SESSION.get(url, timeout=25)
        if r.status_code != 200:
            return (ticker, None)
        text = r.text
        def num(key):
            m = re.search(key + r':"([\d,\.]+)([TBM]?)"', text)
            if not m:
                return None
            v = float(m.group(1).replace(",", ""))
            u = m.group(2)
            if u == "T": v *= 1e12
            elif u == "B": v *= 1e9
            elif u == "M": v *= 1e6
            return v
        mc = num(r'marketCap')
        pe = num(r'peRatio')
        pb = num(r'pbRatio')
        if mc:
            mc = mc / 1e6
        return (ticker, (mc, pe, pb))
    except Exception:
        return (ticker, None)

def main():
    dry = "--dry-run" in sys.argv
    conn = sqlite3.connect(r"D:\2hao-analyst\data\us_stocks.db")
    cur = conn.cursor()
    rows = cur.execute("SELECT ticker FROM us_stocks WHERE market_cap IS NULL OR pe_ttm IS NULL OR pb IS NULL").fetchall()
    tickers = [t[0] for t in rows]
    print(f"待补 {len(tickers)} 只")
    results = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_quote, t): t for t in tickers}
        for i, fut in enumerate(as_completed(futs)):
            t, q = fut.result()
            if q and (q[0] or q[1] or q[2]):
                results[t] = q
            if (i+1) % 40 == 0:
                print(f"进度 {i+1}/{len(tickers)} 成功 {len(results)}")
    ok = 0
    for t, q in results.items():
        if not dry:
            cur.execute("UPDATE us_stocks SET market_cap=?, pe_ttm=?, pb=? WHERE ticker=?", (q[0], q[1], q[2], t))
        ok += 1
    if not dry:
        conn.commit()
    conn.close()
    print(f"成功 {ok}/{len(tickers)}")
    fails = [t for t in tickers if t not in results]
    if fails:
        print("失败:", fails)

if __name__ == "__main__":
    main()
