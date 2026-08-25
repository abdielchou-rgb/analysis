# -*- coding: utf-8 -*-
"""Round5 F: 补抓美股市值/PE/PB (stockanalysis.com quote 页)"""

import re
import sqlite3
import sys
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def fetch_quote(ticker):
    url = f"https://stockanalysis.com/stocks/{ticker}/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        text = r.text
        mc = pe = pb = None
        # Market Cap: <div class="...">$4.569T</div> 或 $3.46B 等
        m = re.search(r"Market Cap[^<]*<[^>]*>\s*\$([\d,\.]+)([TBM]?)", text)
        if m:
            v = float(m.group(1).replace(",", ""))
            u = m.group(2)
            if u == "T":
                v *= 1e12
            elif u == "B":
                v *= 1e9
            elif u == "M":
                v *= 1e6
            mc = v / 1e6  # 统一百万美元
        m = re.search(r"PE Ratio[^<]*<[^>]*>\s*([\d,\.]+)", text)
        if m:
            pe = float(m.group(1).replace(",", ""))
        m = re.search(r"PB Ratio[^<]*<[^>]*>\s*([\d,\.]+)", text)
        if m:
            pb = float(m.group(1).replace(",", ""))
        return (mc, pe, pb)
    except Exception as e:
        return None


def main():
    dry = "--dry-run" in sys.argv
    conn = sqlite3.connect(r"D:\2hao-analyst\data\us_stocks.db")
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT ticker FROM us_stocks WHERE market_cap IS NULL OR pe_ttm IS NULL OR pb IS NULL"
    ).fetchall()
    print(f"待补 {len(rows)} 只")
    ok = 0
    for (t,) in rows:
        q = fetch_quote(t)
        if q and (q[0] or q[1] or q[2]):
            if not dry:
                cur.execute("UPDATE us_stocks SET market_cap=?, pe_ttm=?, pb=? WHERE ticker=?", (q[0], q[1], q[2], t))
            ok += 1
        time.sleep(0.6)
    if not dry:
        conn.commit()
    conn.close()
    print(f"成功 {ok}/{len(rows)}")


if __name__ == "__main__":
    main()
