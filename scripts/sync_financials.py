#!/usr/bin/env python3
"""2hao-analyst 财务层同步脚本 — Baostock 季度财务数据 → 本地 SQLite

把 Baostock 的利润表/资产负债表/现金流按季度拉取，存本地。
供报告/图表生成时，即使 akshare 实时财务接口不可用，也有本地财务数据兜底。

用法:
    python scripts/sync_financials.py "600519"             # 同步单只（全量）
    python scripts/sync_financials.py "600519" --incremental  # 只拉新季度
    python scripts/sync_financials.py --all                # 全量同步所有 instruments
    python scripts/sync_financials.py --status             # 查看财务库状态

数据源: Baostock（免费、免token、字段稳定）
  - query_profit_data    利润表: 营收/净利润/毛利率
  - query_balance_data   资产负债表: 总资产/总负债/股东权益
  - query_cash_flow_data 现金流量表: 经营/投资/筹资现金流
"""

import argparse
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "data" / "financials.db"
INSTRUMENTS = _ROOT / "data" / "qlib_bin" / "instruments" / "all.txt"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("sync_fin")

_HAS_BAOSTOCK = False
try:
    import baostock as bs

    _HAS_BAOSTOCK = True
except ImportError:
    logger.warning("baostock 未安装")

_BS_LOGGED_IN = False


# ──────────────────────────────────────────────────────────────
# Baostock 连接
# ──────────────────────────────────────────────────────────────


def _bs_login():
    global _BS_LOGGED_IN
    if not _HAS_BAOSTOCK:
        return False
    if _BS_LOGGED_IN:
        return True
    try:
        lg = bs.login()
        if lg.error_code == "0":
            _BS_LOGGED_IN = True
            return True
        logger.warning("baostock login failed: %s", lg.error_msg)
    except Exception as e:
        logger.warning("baostock login exception: %s", e)
    return False


def to_bs_code(code: str) -> str:
    """600519 → sh.600519"""
    code = code.strip().upper()
    if code.startswith(("SH", "SZ", "BJ")):
        return f"{code[:2].lower()}.{code[2:]}"
    if code.isdigit():
        c = code.zfill(6)
        if c.startswith(("6", "9")):
            return f"sh.{c}"
        return f"sz.{c}"
    return code


def read_instruments(include_inactive: bool = False) -> list[str]:
    """读取 instruments，过滤无效目标。

    过滤规则：
      1. 北交所(BJ) — Baostock 不支持
      2. 指数(SH000xxx / SZ399xxx) — 非个股，无财务数据意义
      3. 退市股（第三列退市日期 < 2025）— 默认跳过（--include-inactive 可选）

    instruments 每行格式: CODE\t上市日期\t退市/最后更新日期
    """
    if not INSTRUMENTS.exists():
        return []
    result = []
    for line in INSTRUMENTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0]
        # 1. 北交所
        if code.startswith("BJ"):
            continue
        # 2. 指数
        if code.startswith("SH000") or code.startswith("SZ399"):
            continue
        # 3. 退市股（第三列日期 < 2025-01-01）
        if not include_inactive and len(parts) >= 3:
            end_date = parts[2]
            if len(end_date) >= 4 and end_date[:4].isdigit() and end_date[:4] < "2025":
                continue
        result.append(code)
    return result


# ──────────────────────────────────────────────────────────────
# SQLite 存储
# ──────────────────────────────────────────────────────────────


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS financials (
            code TEXT NOT NULL,
            quarter TEXT NOT NULL,
            table_name TEXT NOT NULL,
            field TEXT NOT NULL,
            value REAL,
            source TEXT DEFAULT 'baostock',
            PRIMARY KEY (code, quarter, table_name, field)
        )
    """)
    # 迁移：旧库无 source 列 → 添加
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(financials)")}
        if "source" not in cols:
            conn.execute("ALTER TABLE financials ADD COLUMN source TEXT DEFAULT 'baostock'")
            conn.commit()
            logger.info("[MIGRATE] financials 表新增 source 列（默认 baostock）")
    except Exception as e:
        logger.warning("[MIGRATE] source 列迁移失败: %s", e)
    conn.commit()
    return conn


def _get_latest_quarter(code: str) -> str:
    """查询库内该股票最新季度（用于增量同步）。

    仅按 profit 表判断：财务库以利润表为核心，akshare 增量层也只补 profit。
    balance/cashflow 的历史层由 sync_financials 独立拉取（见 _get_table_quarters）。
    """
    return _get_table_latest_quarter(code, "profit")


def _get_table_latest_quarter(code: str, table_name: str) -> str:
    """查询库内该股票指定表的最新季度。"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        r = conn.execute(
            "SELECT MAX(quarter) FROM financials WHERE code=? AND table_name=?", (code, table_name)
        ).fetchone()
        conn.close()
        return r[0] or ""
    except Exception:
        return ""


def _get_table_quarters(code: str) -> dict:
    """按表返回库内已有季度集合 {table_name: set(quarter)}。

    增量同步的核心判断必须按表拆分：
      - 利润表（akshare 覆盖，最新可到 2026Q2）
      - 资产负债表 / 现金流量表（Baostock 历史层，滞后约 3 季度）
    若只取整体 MAX(quarter)，balance/cashflow 缺 2026 数据会被 profit 的最新季度
    掩盖，导致增量跑批时这些表永远不补 → 覆盖率停留在 ~3%。
    """
    out = {t: set() for t in ("profit", "balance", "cashflow")}
    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT DISTINCT table_name, quarter FROM financials WHERE code=?", (code,)).fetchall()
        conn.close()
        for t, q in rows:
            if t in out:
                out[t].add(q)
    except Exception:
        pass
    return out


def _missing_years_for_table(code: str, table_name: str, start_year: int = 2015) -> list[int]:
    """计算单张表需要拉取的年份列表（增量核心，按表独立）。

    库内该表最新季度为 2025-09-30 → 需要 2025（含 Q4 12-31）、2026 的新季度。
    profit 表被 akshare 补到 2026 → 返回 []（不重复拉）。
    """
    latest = _get_table_latest_quarter(code, table_name)
    current_year = datetime.now().year
    if not latest:
        return list(range(start_year, current_year + 1))
    latest_year = int(latest[:4])
    # 需要从最新季度所在年份开始拉（因为该年 Q4 可能还没入库）
    return list(range(latest_year, current_year + 1))


def _missing_years(code: str, start_year: int = 2015) -> list[int]:
    """计算需要拉取的年份列表（增量核心，向后兼容）。

    库内最新季度为 2025-09-30 → 需要 2025（含 Q4 12-31）、2026 的新季度。
    只拉「覆盖最新季度的年份」及之后的年份，大幅减少请求数。
    """
    latest = _get_latest_quarter(code)
    current_year = datetime.now().year
    if not latest:
        return list(range(start_year, current_year + 1))
    # 库内最新季度年份（如 2025）
    latest_year = int(latest[:4])
    # 需要从最新季度所在年份开始拉（因为该年 Q4 可能还没入库）
    return list(range(latest_year, current_year + 1))


def fetch_financials(code: str, incremental: bool = False) -> dict:
    """拉取一只股票的季度财务数据。

    incremental=True: 只拉库内缺失的年份（增量，快）。
    incremental=False: 全量拉 2015 至今。

    增量模式按表独立计算缺失年份：
      - profit（akshare 覆盖到 2026Q2）→ 通常无缺，不重复拉
      - balance/cashflow（Baostock 历史层）→ 缺 2026 时补拉
    避免 profit 的最新季度掩盖 balance/cashflow 的滞后缺口。

    返回 {table_name: [(quarter, field, value), ...]}
    """
    if not _bs_login():
        return {}
    bs_code = to_bs_code(code)
    bs_code_for_query = bs_code
    result = {}
    queries = [
        (
            "profit",
            bs.query_profit_data,
            [
                "code",
                "pubDate",
                "statDate",
                "roeAvg",
                "npMargin",
                "gpMargin",
                "netProfit",
                "epsTTM",
                "MBRevenue",
                "totalShare",
                "liqaShare",
            ],
        ),
        (
            "balance",
            bs.query_balance_data,
            [
                "code",
                "pubDate",
                "statDate",
                "totalShare",
                "liqaShare",
                "totalAssets",
                "totalLiab",
                "totalEquity",
                "cashAssets",
                "advanceReceived",
                "notesPayable",
            ],
        ),
        (
            "cashflow",
            bs.query_cash_flow_data,
            [
                "code",
                "pubDate",
                "statDate",
                "CAToAsset",
                "NCAToAsset",
                "tangibleAssetToAsset",
                "ebitToInterest",
                "OCFToAsset",
                "OCFToOR",
                "OCFToNetprofit",
            ],
        ),
    ]
    current_year = datetime.now().year
    if incremental:
        # 按表独立判断：只有缺当年数据的表才拉（避免利润表掩盖 balance/cashflow 缺口）
        table_quarters = _get_table_quarters(code)
        years_by_table = {}
        for table_name, _, _ in queries:
            latest = max(table_quarters.get(table_name) or {""})
            if not latest or latest[:4] != str(current_year):
                years_by_table[table_name] = _missing_years_for_table(code, table_name)
            else:
                years_by_table[table_name] = []
        logger.debug("[INC] %s 增量各表年份: %s", code, years_by_table)
    for table_name, query_fn, fields in queries:
        try:
            records = []
            if incremental:
                years = years_by_table.get(table_name, [])
            else:
                years = list(range(2015, current_year + 1))
            for year in years:
                rs = query_fn(bs_code_for_query, year=str(year), quarter="")
                if rs.error_code != "0":
                    continue
                while rs.next():
                    r = rs.get_row_data()
                    if len(r) >= 3:
                        quarter = r[2] if len(r) > 2 else ""
                        for i, field in enumerate(fields):
                            if i >= len(r):
                                break
                            val = r[i]
                            try:
                                records.append((quarter, field, float(val)))
                            except (ValueError, TypeError):
                                pass
            result[table_name] = records
        except Exception as e:
            logger.warning("baostock %s for %s failed: %s", table_name, code, e)
    return result


def save_financials(code: str, data: dict) -> int:
    """写入 SQLite，返回记录数。使用 WAL 模式支持多进程并发写。"""
    if not data:
        return 0
    conn = _connect()
    conn.execute("PRAGMA journal_mode=WAL")
    count = 0
    for table_name, records in data.items():
        for quarter, field, value in records:
            if not quarter or not field:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO financials (code, quarter, table_name, field, value, source) "
                "VALUES (?,?,?,?,?, 'baostock')",
                (code, quarter, table_name, field, value),
            )
            count += 1
    conn.commit()
    conn.close()
    return count


def sync_instrument(code: str, incremental: bool = False) -> bool:
    """同步单只股票财务数据"""
    code_clean = code[-6:] if len(code) >= 6 else code
    # 北交所
    if code_clean.startswith(("4", "8")):
        logger.debug("%s 北交所，Baostock 不支持，跳过", code_clean)
        return False
    data = fetch_financials(code_clean, incremental=incremental)
    if not data:
        logger.warning("%s 无财务数据", code_clean)
        return False
    n = save_financials(code_clean, data)
    logger.info("[OK] %s: %d 条财务记录%s", code_clean, n, " (增量)" if incremental else "")
    return True


# 多进程 worker（Baostock 客户端基于全局 socket，进程内线程并发会数据交错）
def _worker_init():
    """进程内初始化：独立 Baostock login。"""
    global _BS_LOGGED_IN
    _BS_LOGGED_IN = False
    if _HAS_BAOSTOCK:
        try:
            lg = bs.login()
            _BS_LOGGED_IN = lg.error_code == "0"
        except Exception:
            _BS_LOGGED_IN = False


def _worker_sync(args: tuple) -> tuple:
    """进程池 worker：同步单只，返回 (code, ok, n_records, error)"""
    code, incremental = args
    code_clean = code[-6:] if len(code) >= 6 else code
    try:
        # 增量模式下：三张表都已有本年数据才算 up_to_date
        # 修复：原逻辑只看 profit 最新季度，导致 balance/cashflow 缺 2026 被掩盖（覆盖率 ~3%）
        if incremental:
            current_year = str(datetime.now().year)
            table_quarters = _get_table_quarters(code_clean)
            all_current = all(
                max(table_quarters.get(t) or {""})[:4] == current_year for t in ("profit", "balance", "cashflow")
            )
            if all_current:
                return (code_clean, True, 0, "skip_up_to_date")
        data = fetch_financials(code_clean, incremental=incremental)
        if not data:
            return (code_clean, False, 0, "no_data")
        n = save_financials(code_clean, data)
        return (code_clean, True, n, "")
    except Exception as e:
        return (code_clean, False, 0, str(e)[:200])


def status():
    if not DB_PATH.exists():
        print("财务库不存在，先运行同步")
        return
    conn = sqlite3.connect(str(DB_PATH))
    n_codes = conn.execute("SELECT COUNT(DISTINCT code) FROM financials").fetchone()[0]
    n_rows = conn.execute("SELECT COUNT(*) FROM financials").fetchone()[0]
    print(f"财务库: {n_codes} 只股票, {n_rows} 条记录")
    # 最近更新的
    recent = conn.execute(
        "SELECT code, quarter, COUNT(*) FROM financials GROUP BY code, quarter ORDER BY quarter DESC LIMIT 5"
    ).fetchall()
    for c, q, n in recent:
        print(f"  {c}: {q} ({n} 字段)")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="财务层同步（Baostock → SQLite）")
    parser.add_argument("asset", nargs="?", help="股票代码，如 600519")
    parser.add_argument("--all", action="store_true", help="全量同步所有 instruments")
    parser.add_argument("--batch", type=int, metavar="N", help="批量同步前 N 只")
    parser.add_argument("--workers", type=int, default=4, help="并发进程数（Baostock 需进程级隔离）")
    parser.add_argument(
        "--incremental", "-i", action="store_true", help="增量同步：只拉库内缺失年份（推荐，快 3-5 倍）"
    )
    parser.add_argument("--include-inactive", action="store_true", help="包含退市股（默认跳过）")
    parser.add_argument("--status", action="store_true", help="查看财务库状态")
    args = parser.parse_args()

    if args.status:
        status()
        return 0

    if not _HAS_BAOSTOCK:
        print("[!!] baostock 未安装，请先 pip install baostock")
        return 1

    targets = []
    if args.all:
        targets = read_instruments(include_inactive=args.include_inactive)
        logger.info("全量财务同步：%d 只（已过滤指数/北交所）", len(targets))
    elif args.batch:
        targets = read_instruments(include_inactive=args.include_inactive)[: args.batch]
        logger.info("批量同步 %d 只（%s）", len(targets), "增量" if args.incremental else "全量")
    elif args.asset:
        targets = [args.asset]
    else:
        parser.print_help()
        return 1

    ok = 0
    skipped = 0
    total = len(targets)
    if total <= 1 or args.workers <= 1:
        # 串行
        for i, t in enumerate(targets, 1):
            try:
                if sync_instrument(t, incremental=args.incremental):
                    ok += 1
            except Exception as e:
                logger.error("%s 失败: %s", t, e)
            time.sleep(0.3)
    else:
        # 多进程：Baostock 客户端基于全局 socket，线程并发会数据交错/超时
        from concurrent.futures import ProcessPoolExecutor
        from concurrent.futures import as_completed as _ac

        with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init) as pool:
            futures = {pool.submit(_worker_sync, (t, args.incremental)): t for t in targets}
            done = 0
            for fut in _ac(futures):
                done += 1
                try:
                    code, ok_flag, n, err = fut.result()
                    if ok_flag:
                        if err == "skip_up_to_date":
                            skipped += 1
                        else:
                            ok += 1
                            logger.info("[OK] %s: %d 条%s", code, n, " (增量)" if args.incremental else "")
                    else:
                        logger.warning("%s 失败: %s", code, err)
                except Exception as e:
                    logger.error("%s 异常: %s", futures[fut], e)
                if done % 25 == 0:
                    logger.info("进度: %d/%d", done, total)

    print(f"\n[完成] {ok}/{total} 成功 (跳过已最新 {skipped})")
    return 0 if ok + skipped == total else 1


if __name__ == "__main__":
    sys.exit(main())
