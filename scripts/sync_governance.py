# -*- coding: utf-8 -*-
"""
Round3 P1-③ 治理/ESG 同步 — company_events.db 加 governance 表

数据源（akshare）:
  - stock_zh_a_gdhs_detail_em(symbol)   股东户数（个股）
  - stock_esg_hz_sina()                 华证 ESG 评级（全市场一次拉取）
  - stock_gpzy_pledge_ratio_em(date)    股权质押比例（按日全市场）

表: governance(code, date, metric, value, extra, source, updated_at)

规范: source 标注、INSERT OR REPLACE 幂等、BATCH=200、批间 sleep、
      异常隔离、有效性校验、5次退避重试。

用法:
  python scripts/sync_governance.py
  python scripts/sync_governance.py --ticker 603662
  python scripts/sync_governance.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
from datetime import datetime, timedelta

import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "company_events.db")
BATCH = 200
SLEEP = 0.6
FOCUS_TICKERS = ["603662"]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS governance (
            code       TEXT,
            date       TEXT,
            metric     TEXT,
            value      REAL,
            extra      TEXT,
            source     TEXT,
            updated_at TEXT,
            PRIMARY KEY (code, date, metric, source)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gov_code_date ON governance(code, date)")
    conn.commit()
    return conn


def _retry(fn, times=5, base=1.5):
    last = None
    for i in range(times):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(base * (2**i) + 0.5)
    raise last


def _num(value):
    try:
        v = float(value)
        if v != v:
            return None
        return v
    except (TypeError, ValueError):
        return None


def _valid(value) -> bool:
    v = _num(value)
    return v is not None and v != 0


def get_tickers(ticker: str | None) -> list:
    if ticker:
        return [ticker]
    tickers = list(FOCUS_TICKERS)
    try:
        df = ak.index_stock_cons_csindex(symbol="000300")
        if df is not None and not df.empty:
            codes = [str(c).zfill(6) for c in df["成分券代码"].tolist()]
            tickers.extend([c for c in codes if c not in tickers][:50])
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] 获取沪深300成分失败，用兜底池: {e}")
        tickers.extend(
            ["600519", "000858", "601318", "600036", "000333", "300750", "600900", "601398", "600276", "000001"]
        )
    return list(dict.fromkeys(tickers))


def sync_gdhs(conn, tickers, dry_run=False):
    """股东户数（个股）"""
    total = 0
    skipped = 0
    for i, tk in enumerate(tickers):
        try:
            df = _retry(lambda t=tk: ak.stock_zh_a_gdhs_detail_em(symbol=t), times=3)
        except Exception as e:
            print(f"[FAIL] 股东户数 {tk}: {e}")
            continue
        if df is None or df.empty:
            skipped += 1
            continue
        date_col = next((c for c in df.columns if "统计截止日" in str(c) or "日期" in str(c)), None)
        cnt_col = next((c for c in df.columns if "股东户数-本次" in str(c)), None) or next(
            (c for c in df.columns if "股东户数" in str(c) and "截止日" not in str(c)), None
        )
        if not date_col or not cnt_col:
            skipped += 1
            continue
        for _, row in df.iterrows():
            d = str(row[date_col])[:10].replace("-", "")
            if not d or len(d) != 8 or not d.isdigit():
                continue
            val = _num(row[cnt_col])
            if not _valid(val):
                skipped += 1
                continue
            if not dry_run:
                conn.execute(
                    "INSERT OR REPLACE INTO governance (code, date, metric, value, extra, source, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (tk, d, "shareholder_count", val, "", "akshare: stock_zh_a_gdhs_detail_em", _now()),
                )
            total += 1
        if not dry_run and (i + 1) % BATCH == 0:
            conn.commit()
        time.sleep(0.3)
    if not dry_run:
        conn.commit()
    print(f"[OK] 股东户数: 写入 {total} 条, 跳过 {skipped}")
    return total


def sync_esg(conn, dry_run=False):
    """华证 ESG 评级（全市场一次）"""
    try:
        df = _retry(lambda: ak.stock_esg_hz_sina(), times=3)
    except Exception as e:
        print(f"[FAIL] ESG: {e}")
        return 0
    if df is None or df.empty:
        print("[OK] ESG: 无数据")
        return 0
    total = 0
    skipped = 0
    code_col = next((c for c in df.columns if "股票代码" in str(c) or "代码" in str(c)), None)
    score_col = next((c for c in df.columns if "ESG评分" in str(c) or "ESG评级" in str(c)), None)
    date_col = next((c for c in df.columns if "日期" in str(c)), None)
    if not code_col or not score_col:
        print("[FAIL] ESG 列名不匹配:", list(df.columns))
        return 0
    for _, row in df.iterrows():
        code = str(row[code_col]).split(".")[0].zfill(6)
        if len(code) != 6 or not code.isdigit():
            skipped += 1
            continue
        d = str(row[date_col])[:10].replace("-", "") if date_col else datetime.now().strftime("%Y%m%d")
        if not d or len(d) != 8 or not d.isdigit():
            d = datetime.now().strftime("%Y%m%d")
        val = _num(row[score_col])
        if val is None:
            skipped += 1
            continue
        extra = f"grade={row.get('ESG等级', '')}" if "ESG等级" in df.columns else ""
        if not dry_run:
            conn.execute(
                "INSERT OR REPLACE INTO governance (code, date, metric, value, extra, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (code, d, "esg_score", val, extra, "akshare: stock_esg_hz_sina", _now()),
            )
        total += 1
    if not dry_run:
        conn.commit()
    print(f"[OK] ESG: 写入 {total} 条, 跳过 {skipped}")
    return total


def sync_pledge(conn, dry_run=False):
    """股权质押（按最近交易日全市场）"""
    total = 0
    skipped = 0
    d = datetime.now()
    df = None
    for _ in range(7):
        ds = d.strftime("%Y%m%d")
        if d.weekday() < 5:
            try:
                df = _retry(lambda x=ds: ak.stock_gpzy_pledge_ratio_em(date=x), times=3)
                if df is not None and not df.empty:
                    break
            except Exception as e:
                print(f"[FAIL] 质押 {ds}: {e}")
        d -= timedelta(days=1)
    if df is None or df.empty:
        print("[OK] 质押: 无数据")
        return 0
    code_col = next((c for c in df.columns if "股票代码" in str(c)), None)
    date_col = next((c for c in df.columns if "交易日期" in str(c)), None)
    ratio_col = next((c for c in df.columns if "质押比例" in str(c)), None)
    if not code_col or not ratio_col:
        print("[FAIL] 质押列名不匹配:", list(df.columns))
        return 0
    for _, row in df.iterrows():
        code = str(row[code_col]).zfill(6)
        if len(code) != 6 or not code.isdigit():
            skipped += 1
            continue
        dstr = str(row[date_col])[:10].replace("-", "") if date_col else ds
        if not dstr or len(dstr) != 8 or not dstr.isdigit():
            dstr = ds
        val = _num(row[ratio_col])
        if not _valid(val):
            skipped += 1
            continue
        if not dry_run:
            conn.execute(
                "INSERT OR REPLACE INTO governance (code, date, metric, value, extra, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (code, dstr, "pledge_ratio", val, "", "akshare: stock_gpzy_pledge_ratio_em", _now()),
            )
        total += 1
    if not dry_run:
        conn.commit()
    print(f"[OK] 质押: 写入 {total} 条, 跳过 {skipped}")
    return total


def main():
    parser = argparse.ArgumentParser(description="Round3 P1-③ 治理/ESG 同步")
    parser.add_argument("--ticker", default=None, help="仅同步单只股票")
    parser.add_argument("--dry-run", action="store_true", help="试跑不写库")
    parser.add_argument("--no-gdhs", action="store_true", help="跳过股东户数")
    parser.add_argument("--no-esg", action="store_true", help="跳过ESG")
    parser.add_argument("--no-pledge", action="store_true", help="跳过质押")
    args = parser.parse_args()

    tickers = get_tickers(args.ticker)
    print(f"[INFO] 标的池: {len(tickers)} 只 -> {tickers[:10]}...")

    conn = _connect()
    try:
        if not args.no_gdhs:
            sync_gdhs(conn, tickers, args.dry_run)
        if not args.no_esg:
            sync_esg(conn, args.dry_run)
        if not args.no_pledge:
            sync_pledge(conn, args.dry_run)
        print("[DONE] 治理/ESG 同步完成")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
