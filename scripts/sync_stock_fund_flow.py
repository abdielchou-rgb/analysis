# -*- coding: utf-8 -*-
"""
Round3 P0-① 个股资金面同步 — capital_flow.db 加 stock_fund_flow 表

数据源（akshare）:
  - stock_hsgt_individual_em(symbol)      个股北向持仓（每日）
  - stock_margin_detail_sse/szse(date)    个股两融余额（按日全市场）
  - stock_individual_fund_flow(stock)     个股资金流向（每日）
  - stock_lhb_detail_em(start,end)        龙虎榜（个股事件）

规范: source 标注、INSERT OR REPLACE 幂等、BATCH=200、批间 sleep、
      异常隔离、有效性校验（关键字段空/全0跳过）、5次退避重试。

用法:
  python scripts/sync_stock_fund_flow.py                # 沪深300前50 + 柯力传感
  python scripts/sync_stock_fund_flow.py --ticker 603662
  python scripts/sync_stock_fund_flow.py --dry-run      # 试跑不写库
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta

import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "capital_flow.db")
BATCH = 200
SLEEP = 0.6
FOCUS_TICKERS = ["603662"]  # 柯力传感（重点标的，确保覆盖）


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_fund_flow (
            code        TEXT,
            date        TEXT,
            metric      TEXT,
            value       REAL,
            extra       TEXT,
            source      TEXT,
            updated_at  TEXT,
            PRIMARY KEY (code, date, metric, source)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sff_code_date ON stock_fund_flow(code, date)")
    conn.commit()
    return conn


def _retry(fn, times=5, base=1.5):
    last = None
    for i in range(times):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(base * (2 ** i) + 0.5)
    raise last


def _valid(value) -> bool:
    try:
        v = float(value)
        return v == v and v not in (0.0,)  # NaN 剔除；0 视为无效占位
    except (TypeError, ValueError):
        return False


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        tickers.extend(["600519", "000858", "601318", "600036", "000333", "300750", "600900", "601398", "600276", "000001"])
    return list(dict.fromkeys(tickers))


def sync_northbound_holding(conn, tickers, dry_run=False):
    """个股北向持仓（沪股通/深股通持股明细）"""
    total = 0
    skipped = 0
    for i, tk in enumerate(tickers):
        try:
            df = _retry(lambda t=tk: ak.stock_hsgt_individual_em(symbol=t))
        except Exception as e:
            print(f"[FAIL] 北向 {tk}: {e}")
            continue
        if df is None or df.empty:
            skipped += 1
            continue
        date_col = next((c for c in df.columns if "日期" in str(c) or "date" in str(c).lower()), None)
        if not date_col:
            skipped += 1
            continue
        # 列名映射（不同市场列略有差异）
        share_col = next((c for c in df.columns if "持股数量" in str(c)), None)
        for _, row in df.iterrows():
            d = str(row[date_col])[:10].replace("-", "")
            if not d or len(d) != 8 or not d.isdigit():
                continue
            val = _num(row[share_col]) if share_col else None
            if not _valid(val):
                skipped += 1
                continue
            if not dry_run:
                conn.execute(
                    "INSERT OR REPLACE INTO stock_fund_flow (code, date, metric, value, extra, source, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (tk, d, "north_hold_shares", val, "", "akshare: stock_hsgt_individual_em", _now()),
                )
            total += 1
        if not dry_run and (i + 1) % BATCH == 0:
            conn.commit()
            time.sleep(SLEEP)
        time.sleep(0.3)
    if not dry_run:
        conn.commit()
    print(f"[OK] 北向持仓: 写入 {total} 条, 跳过 {skipped}")
    return total


def sync_margin(conn, dry_run=False, start=None):
    """个股两融余额：按日全市场（SSE/SZSE）"""
    total = 0
    skipped = 0
    # 最近交易日回退扫描（最多 10 天）
    dates = []
    d = datetime.strptime(start, "%Y%m%d") if start else datetime.now()
    for _ in range(10):
        ds = d.strftime("%Y%m%d")
        # 跳过周末
        if d.weekday() < 5:
            dates.append(ds)
        d -= timedelta(days=1)
        if len(dates) >= 3:
            break

    for ds in dates:
        for mkt, fn in [("sse", ak.stock_margin_detail_sse), ("szse", ak.stock_margin_detail_szse)]:
            try:
                df = _retry(lambda f=fn, x=ds: f(date=x), times=3)
            except Exception as e:
                print(f"[FAIL] 两融 {mkt} {ds}: {e}")
                continue
            if df is None or df.empty:
                continue
            code_col = next((c for c in df.columns if "证券代码" in str(c) or "代码" in str(c)), None)
            bal_col = next((c for c in df.columns if "融资余额" in str(c)), None)
            buy_col = next((c for c in df.columns if "融资买入额" in str(c)), None)
            if not code_col:
                skipped += len(df)
                continue
            for _, row in df.iterrows():
                code = str(row[code_col]).zfill(6)
                if len(code) != 6 or not code.isdigit():
                    skipped += 1
                    continue
                bal = _num(row[bal_col]) if bal_col else None
                if not _valid(bal):
                    skipped += 1
                    continue
                buy = _num(row[buy_col]) if buy_col else None
                if not dry_run:
                    conn.execute(
                        "INSERT OR REPLACE INTO stock_fund_flow (code, date, metric, value, extra, source, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (code, ds, "margin_balance", bal, f"margin_buy={buy or 0}", "akshare: stock_margin_detail_" + mkt, _now()),
                    )
                total += 1
            if not dry_run:
                conn.commit()
            time.sleep(SLEEP)
    if not dry_run:
        conn.commit()
    print(f"[OK] 两融: 写入 {total} 条, 跳过 {skipped}")
    return total


def sync_lhb(conn, dry_run=False):
    """龙虎榜：最近 7 日"""
    total = 0
    skipped = 0
    end = datetime.now()
    start = end - timedelta(days=7)
    try:
        df = _retry(lambda: ak.stock_lhb_detail_em(
            start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d")), times=3)
    except Exception as e:
        print(f"[FAIL] 龙虎榜: {e}")
        return 0
    if df is None or df.empty:
        print("[OK] 龙虎榜: 无数据")
        return 0
    code_col = "代码" if "代码" in df.columns else df.columns[1]
    date_col = "上榜日" if "上榜日" in df.columns else None
    net_col = "龙虎榜净买额" if "龙虎榜净买额" in df.columns else None
    for _, row in df.iterrows():
        code = str(row[code_col]).zfill(6)
        if len(code) != 6 or not code.isdigit():
            skipped += 1
            continue
        d = str(row[date_col])[:10].replace("-", "") if date_col else start.strftime("%Y%m%d")
        if not d or len(d) != 8 or not d.isdigit():
            d = start.strftime("%Y%m%d")
        net = _num(row[net_col]) if net_col else None
        if not _valid(net):
            skipped += 1
            continue
        if not dry_run:
            conn.execute(
                "INSERT OR REPLACE INTO stock_fund_flow (code, date, metric, value, extra, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (code, d, "lhb_net_buy", net, "", "akshare: stock_lhb_detail_em", _now()),
            )
        total += 1
    if not dry_run:
        conn.commit()
    print(f"[OK] 龙虎榜: 写入 {total} 条, 跳过 {skipped}")
    return total


def sync_individual_fund_flow(conn, tickers, dry_run=False):
    """个股资金流向（东财接口偶发断连，尽力而为）"""
    total = 0
    skipped = 0
    for i, tk in enumerate(tickers):
        market = "sh" if tk.startswith(("6", "9")) else "sz"
        try:
            df = _retry(lambda t=tk, m=market: ak.stock_individual_fund_flow(stock=t, market=m), times=3)
        except Exception as e:
            print(f"[FAIL] 资金流向 {tk}: {e}")
            continue
        if df is None or df.empty:
            skipped += 1
            continue
        date_col = next((c for c in df.columns if "日期" in str(c)), None)
        main_col = next((c for c in df.columns if "主力净流入" in str(c)), None)
        if not date_col or not main_col:
            skipped += 1
            continue
        for _, row in df.iterrows():
            d = str(row[date_col])[:10].replace("-", "")
            if not d or len(d) != 8 or not d.isdigit():
                continue
            val = _num(row[main_col])
            if not _valid(val):
                skipped += 1
                continue
            if not dry_run:
                conn.execute(
                    "INSERT OR REPLACE INTO stock_fund_flow (code, date, metric, value, extra, source, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (tk, d, "main_net_inflow", val, "", "akshare: stock_individual_fund_flow", _now()),
                )
            total += 1
        if not dry_run and (i + 1) % BATCH == 0:
            conn.commit()
            time.sleep(SLEEP)
        time.sleep(0.3)
    if not dry_run:
        conn.commit()
    print(f"[OK] 资金流向: 写入 {total} 条, 跳过 {skipped}")
    return total


def main():
    parser = argparse.ArgumentParser(description="Round3 P0-① 个股资金面同步")
    parser.add_argument("--ticker", default=None, help="仅同步单只股票")
    parser.add_argument("--dry-run", action="store_true", help="试跑不写库")
    parser.add_argument("--no-north", action="store_true", help="跳过北向持仓")
    parser.add_argument("--no-margin", action="store_true", help="跳过两融")
    parser.add_argument("--no-lhb", action="store_true", help="跳过龙虎榜")
    parser.add_argument("--no-flow", action="store_true", help="跳过个股资金流向")
    args = parser.parse_args()

    tickers = get_tickers(args.ticker)
    print(f"[INFO] 标的池: {len(tickers)} 只 -> {tickers[:10]}...")

    conn = _connect()
    try:
        if not args.no_north:
            sync_northbound_holding(conn, tickers, args.dry_run)
        if not args.no_margin:
            sync_margin(conn, args.dry_run)
        if not args.no_lhb:
            sync_lhb(conn, args.dry_run)
        if not args.no_flow:
            sync_individual_fund_flow(conn, tickers, args.dry_run)
        print("[DONE] 个股资金面同步完成")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
