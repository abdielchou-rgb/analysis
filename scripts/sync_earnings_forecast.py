#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""业绩预告/快报同步 — R30 模块7：预期差引擎的数据源

由 Marvis 在用户机执行（akshare 可用）。拉取 A 股业绩预告/快报 → earnings_forecast.db。

用法：
  python scripts/sync_earnings_forecast.py              # 全量同步
  python scripts/sync_earnings_forecast.py --code 603662  # 单只
"""

import argparse
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

DB = _ROOT / "data" / "earnings_forecast.db"


def _connect():
    conn = sqlite3.connect(str(DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS earnings_forecast (
            code TEXT NOT NULL,
            announce_date TEXT,
            forecast_type TEXT,        -- 预告/快报
            forecast_net_profit REAL,   -- 预告净利（万元）
            forecast_growth REAL,       -- 预告增速（%）
            source TEXT,
            PRIMARY KEY (code, announce_date)
        )
    """)
    return conn


def sync_all(limit: int = 300):
    """同步沪深300 成分股的业绩预告/快报。"""
    import akshare as ak

    conn = _connect()
    ok = 0
    try:
        # 全市场业绩预告
        df = ak.stock_yjyg_em(date="20260630")
        if df is not None and len(df) > 0:
            for _, row in df.iterrows():
                code = str(row.get("股票代码", "")).zfill(6)
                if not code or code == "000000":
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO earnings_forecast "
                    "(code, announce_date, forecast_type, forecast_net_profit, forecast_growth, source) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        code,
                        str(row.get("公告日期", ""))[:10],
                        "预告",
                        _num(row.get("预测净利润中值")) or _num(row.get("预测净利润上限")),
                        _num(row.get("业绩变动幅度")),
                        "akshare:stock_yjyg_em",
                    ),
                )
            conn.commit()
            ok += len(df)
        print(f"业绩预告同步: {ok} 条")
    except Exception as e:
        print(f"业绩预告同步失败: {e}")
    conn.close()
    return ok


def _num(v):
    try:
        if v is None:
            return None
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", help="单只股票代码")
    args = parser.parse_args()
    if args.code:
        import akshare as ak

        conn = _connect()
        df = ak.stock_yjyg_em(date="20260630")
        rows = df[df["股票代码"] == args.code] if df is not None else None
        if rows is not None and len(rows) > 0:
            for _, r in rows.iterrows():
                conn.execute(
                    "INSERT OR REPLACE INTO earnings_forecast "
                    "(code, announce_date, forecast_type, forecast_net_profit, forecast_growth, source) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        args.code,
                        str(r.get("公告日期", ""))[:10],
                        "预告",
                        _num(r.get("预测净利润中值")),
                        _num(r.get("业绩变动幅度")),
                        "akshare:stock_yjyg_em",
                    ),
                )
            conn.commit()
            print(f"{args.code}: {len(rows)} 条预告")
        else:
            print(f"{args.code}: 无预告")
        conn.close()
    else:
        sync_all()


if __name__ == "__main__":
    main()
