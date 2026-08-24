# -*- coding: utf-8 -*-
"""
Round3 P0-② 一致预期/市场共识同步 — 新建 consensus_estimates.db

数据源（akshare）:
  - stock_profit_forecast_ths(symbol, indicator="预测年报每股收益")  未来3年EPS预测
  - stock_research_report_em(symbol)                                 分析师评级+盈利预测

表: consensus(code, as_of, eps_2026e, eps_2027e, eps_2028e,
              target_price_avg, rating_buy, rating_hold, rating_sell,
              n_analysts, source)

规范: source 标注、INSERT OR REPLACE 幂等、BATCH=200、批间 sleep、
      异常隔离、有效性校验、5次退避重试。

用法:
  python scripts/sync_consensus_estimates.py
  python scripts/sync_consensus_estimates.py --ticker 603662
  python scripts/sync_consensus_estimates.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import time
from datetime import datetime

import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "consensus_estimates.db")
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
    # R53 P0-2：主键升级为 (code, as_of, updated_at)，保留每日快照历史；
    # 新增 revision_slope / revision_breadth 派生列（采集层计算）。
    has_v2 = False
    cur = conn.execute("PRAGMA table_info(consensus)")
    for row in cur.fetchall():
        if row[1] == "revision_slope":
            has_v2 = True
    if not has_v2:
        try:
            conn.execute("ALTER TABLE consensus RENAME TO consensus_v1")
        except sqlite3.OperationalError:
            pass  # 表不存在
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consensus (
                code           TEXT,
                as_of          TEXT,
                eps_2026e      REAL,
                eps_2027e      REAL,
                eps_2028e      REAL,
                target_price_avg REAL,
                rating_buy     INTEGER,
                rating_hold    INTEGER,
                rating_sell    INTEGER,
                n_analysts     INTEGER,
                source         TEXT,
                updated_at     TEXT,
                revision_slope REAL,
                revision_breadth REAL,
                PRIMARY KEY (code, as_of, updated_at)
            )
        """)
        # 旧快照迁移：保留 v1 数据（updated_at=as_of 00:00:00 可辨识）
        try:
            conn.execute("""
                INSERT OR IGNORE INTO consensus
                    (code, as_of, eps_2026e, eps_2027e, eps_2028e, target_price_avg,
                     rating_buy, rating_hold, rating_sell, n_analysts, source, updated_at)
                SELECT code, as_of, eps_2026e, eps_2027e, eps_2028e, target_price_avg,
                       rating_buy, rating_hold, rating_sell, n_analysts, source, as_of
                FROM consensus_v1
            """)
            conn.execute("DROP TABLE consensus_v1")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return conn


def _retry(fn, times=8, base=1.5):
    last = None
    for i in range(times):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(base * (2 ** i) + 0.5)
    raise last


def _num(value):
    try:
        v = float(value)
        if v != v:
            return None
        return v
    except (TypeError, ValueError):
        return None


def get_tickers(ticker: str | None, index: str | None = None) -> list:
    if ticker:
        return [ticker]
    if index:
        # R33：全量指数成分（沪深300/中证1000）；R53：中证官网 excel 接口偶发格式异常 → 新浪源兜底
        try:
            df = ak.index_stock_cons_csindex(symbol=index)
            if df is not None and not df.empty:
                return [str(c).zfill(6) for c in df["成分券代码"].tolist()]
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] index_stock_cons_csindex({index}) 失败: {e}，尝试兜底源")
            time.sleep(2)
        # 兜底1：中证权重接口（稳定）
        try:
            dfw = ak.index_stock_cons_weight_csindex(symbol=index)
            if dfw is not None and not dfw.empty:
                return [str(c).zfill(6) for c in dfw["成分券代码"].tolist()]
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] index_stock_cons_weight_csindex({index}) 失败: {e}")
            time.sleep(2)
        # 兜底2：新浪源
        try:
            df2 = ak.index_stock_cons(symbol=index)
            if df2 is not None and not df2.empty:
                col = "code" if "code" in df2.columns else df2.columns[0]
                return [str(c).zfill(6) for c in df2[col].tolist()]
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] index_stock_cons({index}) 失败: {e}")
        # 兜底3：复用 consensus 表已有 code（保证 P0-2 历史重建不依赖成分接口）
        try:
            conn = _connect()
            rows = conn.execute("SELECT DISTINCT code FROM consensus").fetchall()
            conn.close()
            codes = [str(r[0]).zfill(6) for r in rows]
            if codes:
                print(f"[WARN] 使用 consensus 表已有 {len(codes)} 只 code 作为标的池")
                return codes
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] consensus 兜底失败: {e}")
        raise RuntimeError(f"获取指数{index}成分失败: 全部源均失败")
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


def sync_eps_forecast(conn, tickers, dry_run=False) -> dict:
    """盈利预测：未来3年 EPS（同花顺）"""
    eps_map: dict[str, dict] = {}
    ok = fail = 0
    for i, tk in enumerate(tickers):
        try:
            df = _retry(lambda t=tk: ak.stock_profit_forecast_ths(symbol=t, indicator="预测年报每股收益"), times=3)
        except Exception as e:
            print(f"[FAIL] EPS预测 {tk}: {e}")
            fail += 1
            continue
        if df is None or df.empty:
            fail += 1
            continue
        row = {}
        for _, r in df.iterrows():
            year = str(r.get("年度", ""))
            mean = _num(r.get("均值"))
            if not year or not mean:
                continue
            # 列形如 2026E/2026e/2026
            yy = year.split("E")[0].split("e")[0].strip()
            if yy.endswith("年"):
                yy = yy[:-1]
            if not yy.isdigit():
                continue
            row[f"eps_{yy}e"] = mean
        if not row:
            fail += 1
            continue
        eps_map[tk] = row
        ok += 1
        time.sleep(0.3)
        if not dry_run and (i + 1) % BATCH == 0:
            conn.commit()
    print(f"[OK] EPS预测: 成功 {ok}, 失败 {fail}")
    return eps_map


def sync_analyst_rating(conn, tickers, dry_run=False) -> dict:
    """分析师评级分布 + 盈利预测（东财研报）"""
    rating_map: dict[str, dict] = {}
    ok = fail = 0
    for i, tk in enumerate(tickers):
        try:
            df = _retry(lambda t=tk: ak.stock_research_report_em(symbol=t), times=3)
        except Exception as e:
            print(f"[FAIL] 研报 {tk}: {e}")
            fail += 1
            continue
        if df is None or df.empty:
            fail += 1
            continue
        # 东财评级：买入/增持/中性/减持/卖出 文本列
        rating_col = next((c for c in df.columns if "评级" in str(c) and "数" not in str(c)), None)
        n_analysts = len(df)
        buy = hold = sell = 0
        target_prices = []
        if rating_col:
            for v in df[rating_col].dropna():
                s = str(v)
                if any(k in s for k in ("买入", "强烈推荐", "推荐")):
                    buy += 1
                elif any(k in s for k in ("中性", "持有")):
                    hold += 1
                elif any(k in s for k in ("卖出", "减持", "回避")):
                    sell += 1
        # 目标价：优先取最新一条研报
        for c in df.columns:
            if "目标价" in str(c):
                tp = _num(df[c].dropna().iloc[0]) if not df[c].dropna().empty else None
                if tp:
                    target_prices.append(tp)
        rating_map[tk] = {
            "n_analysts": n_analysts,
            "rating_buy": buy,
            "rating_hold": hold,
            "rating_sell": sell,
            "target_price_avg": sum(target_prices) / len(target_prices) if target_prices else None,
        }
        ok += 1
        time.sleep(0.3)
        if not dry_run and (i + 1) % BATCH == 0:
            conn.commit()
    print(f"[OK] 分析师评级: 成功 {ok}, 失败 {fail}")
    return rating_map


def sync_history(conn, tickers, dry_run=False) -> dict:
    """R53 P0-2：按研报发布日期重建历史预测快照。

    东财研报接口含 '日期'（发布日期）、'东财评级'、'20XX-盈利预测-收益' 列，
    无目标价列（免费源限制，target_price_avg 置 NULL）。
    按天聚合：n_analysts / rating_buy/hold/sell / eps_202Xe 均值。
    """
    ok = fail = 0
    total_rows = 0
    for i, tk in enumerate(tickers):
        try:
            df = _retry(lambda t=tk: ak.stock_research_report_em(symbol=t), times=3)
        except Exception as e:
            print(f"[FAIL] 研报历史 {tk}: {e}")
            fail += 1
            continue
        if df is None or df.empty:
            fail += 1
            continue
        if "日期" not in df.columns:
            fail += 1
            continue
        date_col = "日期"
        rating_col = next((c for c in df.columns if "评级" in str(c) and "数" not in str(c)), None)
        eps_cols = {}
        for c in df.columns:
            mm = __import__("re").match(r"(20\d\d)-盈利预测-收益", str(c))
            if mm:
                eps_cols[mm.group(1)] = c
        by_date: dict[str, dict] = {}
        for _, r in df.iterrows():
            d = str(r.get(date_col, "")).strip()
            if not d or len(d) < 8:
                continue
            dkey = d[:10].replace("-", "")
            if not dkey.isdigit():
                continue
            rec = by_date.setdefault(dkey, {"buy": 0, "hold": 0, "sell": 0, "n": 0,
                                            "eps": {y: [] for y in eps_cols}})
            rec["n"] += 1
            if rating_col:
                s = str(r.get(rating_col, ""))
                if any(k in s for k in ("买入", "强烈推荐", "推荐")):
                    rec["buy"] += 1
                elif any(k in s for k in ("中性", "持有")):
                    rec["hold"] += 1
                elif any(k in s for k in ("卖出", "减持", "回避")):
                    rec["sell"] += 1
            for y, col in eps_cols.items():
                v = _num(r.get(col))
                if v is not None:
                    rec["eps"][y].append(v)
        if not by_date:
            fail += 1
            continue
        src = "akshare: stock_research_report_em (--history 研报日期重建)"
        for dkey in sorted(by_date):
            rec = by_date[dkey]
            if not dry_run:
                conn.execute(
                    "INSERT OR REPLACE INTO consensus "
                    "(code, as_of, eps_2026e, eps_2027e, eps_2028e, target_price_avg, "
                    " rating_buy, rating_hold, rating_sell, n_analysts, source, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        tk, dkey,
                        (sum(rec["eps"]["2026"]) / len(rec["eps"]["2026"])) if rec["eps"].get("2026") else None,
                        (sum(rec["eps"]["2027"]) / len(rec["eps"]["2027"])) if rec["eps"].get("2027") else None,
                        (sum(rec["eps"]["2028"]) / len(rec["eps"]["2028"])) if rec["eps"].get("2028") else None,
                        None,
                        rec["buy"], rec["hold"], rec["sell"], rec["n"],
                        src, f"{dkey} 12:00:00",
                    ),
                )
        total_rows += len(by_date)
        ok += 1
        time.sleep(0.3)
        if not dry_run and (i + 1) % BATCH == 0:
            conn.commit()
    print(f"[OK] 研报历史: 成功 {ok}, 失败 {fail}, 快照 {total_rows} 条")
    return {"ok": ok, "fail": fail, "rows": total_rows}


def compute_revisions(conn, dry_run=False) -> int:
    """R53 P0-2：revision_slope / revision_breadth（采集层派生）。

    slope: 最新与上一历史 as_of 的 eps_2026e 变化率（预测修正方向）
    breadth: 最新快照买入评级占比 - 上一快照买入占比（修正广度）
    """
    codes = [r[0] for r in conn.execute(
        "SELECT DISTINCT code FROM consensus ORDER BY code").fetchall()]
    updated = 0
    for code in codes:
        rows = conn.execute(
            "SELECT as_of, eps_2026e, rating_buy, rating_sell, n_analysts "
            "FROM consensus WHERE code=? AND n_analysts>0 "
            "ORDER BY as_of", (code,)).fetchall()
        if len(rows) < 2:
            continue
        latest, prev = rows[-1], rows[-2]
        slope = None
        if latest[1] is not None and prev[1] not in (None, 0):
            slope = (latest[1] - prev[1]) / abs(prev[1])
        breadth = None
        for r in (latest, prev):
            if r[4] and r[2] is not None:
                pass
        if latest[4] and prev[4] and latest[2] is not None and prev[2] is not None:
            breadth = (latest[2] / latest[4]) - (prev[2] / prev[4])
        if not dry_run:
            conn.execute(
                "UPDATE consensus SET revision_slope=?, revision_breadth=? "
                "WHERE code=? AND as_of=? AND updated_at=?",
                (slope, breadth, code, latest[0],
                 conn.execute("SELECT updated_at FROM consensus WHERE code=? AND as_of=? AND n_analysts>0 ORDER BY updated_at DESC LIMIT 1",
                              (code, latest[0])).fetchone()[0]),
            )
            updated += 1
    if not dry_run:
        conn.commit()
    print(f"[OK] revision 派生: 更新 {updated} 只")
    return updated


def main():
    parser = argparse.ArgumentParser(description="Round3 P0-② 一致预期同步")
    parser.add_argument("--ticker", default=None, help="仅同步单只股票")
    parser.add_argument("--index", default=None, help="指数成分全量同步: 000300/000852")
    parser.add_argument("--dry-run", action="store_true", help="试跑不写库")
    parser.add_argument("--history", action="store_true",
                        help="R53 P0-2: 按研报日期重建历史预测快照并计算 revision 派生字段")
    args = parser.parse_args()

    tickers = get_tickers(args.ticker, args.index)
    print(f"[INFO] 标的池: {len(tickers)} 只 -> {tickers[:10]}...")

    conn = _connect()
    if args.history:
        try:
            sync_history(conn, tickers, args.dry_run)
            if not args.dry_run:
                compute_revisions(conn)
            print("[DONE] 一致预期历史序列重建完成")
        finally:
            conn.close()
        return
    as_of = datetime.now().strftime("%Y%m%d")
    try:
        eps_map = sync_eps_forecast(conn, tickers, args.dry_run)
        rating_map = sync_analyst_rating(conn, tickers, args.dry_run)

        total = 0
        for tk in set(list(eps_map.keys()) + list(rating_map.keys())):
            eps = eps_map.get(tk, {})
            rat = rating_map.get(tk, {})
            # 有效性：EPS 或评级至少有一项真实数据
            has_eps = any(v is not None for v in eps.values())
            has_rat = rat.get("n_analysts", 0) > 0
            if not has_eps and not has_rat:
                continue
            if not args.dry_run:
                conn.execute(
                    "INSERT OR REPLACE INTO consensus "
                    "(code, as_of, eps_2026e, eps_2027e, eps_2028e, target_price_avg, "
                    " rating_buy, rating_hold, rating_sell, n_analysts, source, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        tk, as_of,
                        eps.get("eps_2026e"), eps.get("eps_2027e"), eps.get("eps_2028e"),
                        rat.get("target_price_avg"),
                        rat.get("rating_buy"), rat.get("rating_hold"), rat.get("rating_sell"),
                        rat.get("n_analysts"),
                        "akshare: stock_profit_forecast_ths/stock_research_report_em",
                        _now(),
                    ),
                )
            total += 1
        if not args.dry_run:
            conn.commit()
        print(f"[OK] 一致预期: 写入 {total} 条")
        print("[DONE] 一致预期同步完成")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
