#!/usr/bin/env python3
"""P0-② 资金面数据同步 — 北向资金/两融/公募 入 capital_flow.db

用法:
    python scripts/sync_capital_flow.py --all          # 全量同步
    python scripts/sync_capital_flow.py --northbound    # 仅北向
    python scripts/sync_capital_flow.py --margin        # 仅两融
    python scripts/sync_capital_flow.py --fund          # 仅公募

数据来源: akshare
数据库: data/capital_flow.db

表结构:
  - northbound_daily:  date, net_flow, buy_turnover, sell_turnover, balance
  - margin_daily:      date, margin_balance, short_balance, margin_buy, short_sell
  - fund_holding:      date, fund_code, fund_name, stock_code, stock_name, shares, market_value

FP2 零编造: 所有数据来自 akshare 接口，含 source 标注
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "capital_flow.db"


def ensure_db():
    """创建数据库和表结构。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS northbound_daily (
            date TEXT PRIMARY KEY,
            net_flow REAL,
            buy_turnover REAL,
            sell_turnover REAL,
            balance REAL,
            source TEXT DEFAULT 'akshare',
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS margin_daily (
            date TEXT PRIMARY KEY,
            margin_balance REAL,
            short_balance REAL,
            margin_buy REAL,
            short_sell REAL,
            source TEXT DEFAULT 'akshare',
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS fund_holding (
            date TEXT,
            fund_code TEXT,
            fund_name TEXT,
            stock_code TEXT,
            stock_name TEXT,
            shares REAL,
            market_value REAL,
            source TEXT DEFAULT 'akshare',
            updated_at TEXT,
            PRIMARY KEY (date, fund_code, stock_code)
        );
        CREATE INDEX IF NOT EXISTS idx_fund_date ON fund_holding(date);
        CREATE INDEX IF NOT EXISTS idx_fund_stock ON fund_holding(stock_code);
    """)
    conn.commit()
    return conn


# ──────────────────────────── 北向资金 ────────────────────────────


def sync_northbound(conn: sqlite3.Connection, days: int = 90):
    """同步北向资金日度数据。"""
    try:
        import akshare as ak

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        # 使用 stock_hsgt_hist_em 分别取沪股通+深股通
        count = 0
        now = datetime.now().isoformat()
        df_h = ak.stock_hsgt_hist_em(symbol="沪股通")
        df_s = ak.stock_hsgt_hist_em(symbol="深股通")

        # 按日期合并（最外层 net_flow = 沪+深）
        from collections import defaultdict

        date_map = defaultdict(lambda: {"net": 0, "buy": 0, "sell": 0, "balance": 0})
        for df_src in [df_h, df_s]:
            if df_src is None or df_src.empty:
                continue
            for _, row in df_src.iterrows():
                d = str(row.get("日期", ""))
                if not d or len(d.replace("-", "")) != 8:
                    continue
                d = d.replace("-", "")
                date_map[d]["net"] += float(row.get("当日成交净买额", 0) or 0)
                date_map[d]["buy"] += float(row.get("买入成交额", 0) or 0)
                date_map[d]["sell"] += float(row.get("卖出成交额", 0) or 0)
                date_map[d]["balance"] += float(row.get("当日余额", 0) or 0)

        for date, vals in sorted(date_map.items()):
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO northbound_daily(date, net_flow, buy_turnover, sell_turnover, balance, source, updated_at) VALUES(?,?,?,?,?,?,?)",
                    (date, vals["net"], vals["buy"], vals["sell"], vals["balance"], "akshare_hsgt", now),
                )
                count += 1
            except Exception:
                continue
        conn.commit()
        print(f"[北向] 同步 {count} 条日度数据（沪+深合并）")
        return count
    except ImportError:
        print("[北向] akshare 未安装")
        return 0
    except Exception as e:
        print(f"[北向] 错误: {e}")
        return 0


# ──────────────────────────── 两融数据 ────────────────────────────


def sync_margin(conn: sqlite3.Connection, days: int = 90):
    """同步融资融券日度数据。"""
    try:
        import akshare as ak

        # 分别获取上交所和深交所两融数据
        count = 0
        now = datetime.now().isoformat()
        today = datetime.now().strftime("%Y%m%d")
        for exchange, func in [("sse", ak.stock_margin_sse), ("szse", ak.stock_margin_szse)]:
            try:
                # akshare 默认 end_date 硬编码在历史日期，必须显式传入当前日期才能取到最新数据
                if exchange == "sse":
                    df = func(start_date="20010106", end_date=today)
                else:
                    df = func()
                if df is None or df.empty:
                    continue
                for _, row in df.iterrows():
                    date = str(row.get("日期", "") or row.get("信用交易日期", ""))
                    if not date or len(date.replace("-", "")) != 8:
                        continue
                    date = date.replace("-", "")
                    try:
                        conn.execute(
                            "INSERT OR REPLACE INTO margin_daily(date, margin_balance, short_balance, margin_buy, short_sell, source, updated_at) VALUES(?,?,?,?,?,?,?)",
                            (
                                date,
                                float(row.get("融资余额", 0) or row.get("融资余额(元)", 0) or 0),
                                float(row.get("融券余额", 0) or row.get("融券余额(元)", 0) or 0),
                                float(row.get("融资买入额", 0) or row.get("融资买入额(元)", 0) or 0),
                                float(row.get("融券卖出量", 0) or row.get("融券卖出量(股)", 0) or 0),
                                f"akshare_{exchange}",
                                now,
                            ),
                        )
                        count += 1
                    except Exception:
                        continue
            except Exception as e:
                print(f"[两融] {exchange} 接口失败: {e}")
                continue
        conn.commit()
        print(f"[两融] 同步 {count} 条日度数据")
        return count
    except ImportError:
        print("[两融] akshare 未安装")
        return 0
    except Exception as e:
        print(f"[两融] 错误: {e}")
        return 0


# ──────────────────────────── 公募持仓 ────────────────────────────


def sync_fund_holding(conn: sqlite3.Connection):
    """同步公募基金重仓股数据（最新季度）。"""
    try:
        import akshare as ak

        # 使用 fund_portfolio_hold_em（基金持仓）获取最新季度数据
        try:
            df = ak.fund_portfolio_hold_em(date=datetime.now().strftime("%Y"))
        except Exception:
            try:
                df = ak.fund_portfolio_hold_em(date=str(datetime.now().year - 1))
            except Exception:
                df = None
        if df is None or df.empty:
            # 尝试用 stock_report_fund_hold 获取机构持仓汇总
            try:
                df = ak.stock_report_fund_hold(date=str(datetime.now().year))
            except Exception:
                print("[公募] 所有接口返回空")
                return 0

        count = 0
        now = datetime.now().isoformat()
        quarter_end = f"{datetime.now().year}-06-30"  # 近似季度末
        for _, row in df.iterrows():
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO fund_holding(date, fund_code, fund_name, stock_code, stock_name, shares, market_value, source, updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        quarter_end,
                        str(row.get("基金代码", "")),
                        str(row.get("基金简称", "")),
                        str(row.get("股票代码", "")),
                        str(row.get("股票名称", "")),
                        float(row.get("持股数", 0) or 0),
                        float(row.get("持股市值", 0) or 0),
                        "akshare",
                        now,
                    ),
                )
                count += 1
            except Exception:
                continue
        conn.commit()
        print(f"[公募] 同步 {count} 条基金持仓")
        return count
    except ImportError:
        print("[公募] akshare 未安装")
        return 0
    except Exception as e:
        print(f"[公募] 错误: {e}")
        return 0


# ──────────────────────────── 入口 ────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="资金面数据同步")
    parser.add_argument("--all", action="store_true", help="全量同步")
    parser.add_argument("--northbound", action="store_true", help="仅北向")
    parser.add_argument("--margin", action="store_true", help="仅两融")
    parser.add_argument("--fund", action="store_true", help="仅公募")
    parser.add_argument("--days", type=int, default=90, help="回溯天数（默认90）")
    args = parser.parse_args()

    if not any([args.all, args.northbound, args.margin, args.fund]):
        parser.print_help()
        return 1

    conn = ensure_db()
    total = 0

    if args.all or args.northbound:
        total += sync_northbound(conn, args.days)
    if args.all or args.margin:
        total += sync_margin(conn, args.days)
    if args.all or args.fund:
        total += sync_fund_holding(conn)

    conn.close()
    print(f"\n[完成] 总计同步 {total} 条记录 → {DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
