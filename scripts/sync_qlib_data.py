#!/usr/bin/env python3
"""2hao-analyst Qlib 数据同步脚本 — 用 akshare 更新 data/qlib_bin

把 akshare 拉到的 A 股日线写入 Qlib bin 格式，供报告/图表离线使用。
当 akshare 实时接口不可用时，本地数据作为兜底（"拖底"）。

用法:
    python scripts/sync_qlib_data.py "sh688981"          # 同步单只（全量）
    python scripts/sync_qlib_data.py "sh688981" --incremental  # 增量（只拉新日期）
    python scripts/sync_qlib_data.py --batch 20           # 批量同步前20只（从 all.txt）
    python scripts/sync_qlib_data.py --list "sh600519,sz000001"  # 多只
    python scripts/sync_qlib_data.py --status             # 查看数据仓库状态

已知坑（来自 quant-research 经验）:
    - curl_cffi/akshare 大量连续请求会 RemoteDisconnected → 每请求 sleep + 重试
    - 接口偶发挂起 → 设 timeout
    - 字段名会随 akshare 版本漂移 → 锁定版本 + 宽容解析
"""

import argparse
import json
import logging
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
QLIB_DIR = _ROOT / "data" / "qlib_bin"
CALENDAR = QLIB_DIR / "calendars" / "day.txt"
INSTRUMENTS = QLIB_DIR / "instruments" / "all.txt"
FEATURES = QLIB_DIR / "features"

FIELDS = ["open", "high", "low", "close", "volume", "amount", "factor", "vwap", "change", "adjclose"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("sync_qlib")

_HAS_AKSHARE = False
try:
    import akshare as ak
    _HAS_AKSHARE = True
except ImportError:
    logger.warning("akshare 未安装，只能检查已有数据状态")


# ──────────────────────────────────────────────────────────────
# Qlib bin 读写
# ──────────────────────────────────────────────────────────────

def load_calendar() -> list[str]:
    """加载交易日历，返回日期列表。"""
    if not CALENDAR.exists():
        return []
    return CALENDAR.read_text(encoding="utf-8").splitlines()


def save_calendar(dates: list[str]) -> None:
    """写回交易日历（去重、排序）。"""
    uniq = sorted(set(dates))
    CALENDAR.parent.mkdir(parents=True, exist_ok=True)
    CALENDAR.write_text("\n".join(uniq) + "\n", encoding="utf-8")


def update_calendar(force: bool = False) -> list[str]:
    """更新交易日历到最新。

    优先 Baostock query_trade_dates，akshare tool_trade_date_hist_sina 兜底。
    返回更新后的日历列表。
    """
    cal = load_calendar()
    last = cal[-1] if cal else "2000-01-04"
    today = datetime.now().strftime("%Y-%m-%d")
    if last >= today and not force:
        logger.info("日历已是最新: %s", last)
        return cal

    new_dates = set()
    # 1. Baostock 优先
    if _HAS_BAOSTOCK:
        try:
            lg = bs.login()
            if lg.error_code == "0":
                rs = bs.query_trade_dates(start_date=last, end_date=today)
                while (rs.error_code == "0") and rs.next():
                    row = rs.get_row_data()
                    if len(row) >= 2 and row[1] == "1":  # is_trading_day == 1
                        new_dates.add(row[0])
                bs.logout()
                logger.info("Baostock 日历: %d 个新交易日", len(new_dates))
        except Exception as e:
            logger.warning("Baostock 日历更新失败: %s", e)
            new_dates = set()

    # 2. akshare 兜底
    if not new_dates and _HAS_AKSHARE:
        try:
            df = ak.tool_trade_date_hist_sina()
            if df is not None and "trade_date" in df.columns:
                for d in df["trade_date"].astype(str):
                    if last < d <= today:
                        new_dates.add(d)
                logger.info("akshare 日历: %d 个新交易日", len(new_dates))
        except Exception as e:
            logger.warning("akshare 日历更新失败: %s", e)

    if not new_dates:
        logger.warning("日历更新失败：两个数据源均不可用")
        return cal

    updated = sorted(set(cal + list(new_dates)))
    save_calendar(updated)
    logger.info("日历已更新: %s -> %s (%d -> %d 天)",
                last, updated[-1], len(cal), len(updated))
    return updated


def instrument_key(asset: str) -> str:
    """把资产名规范为 Qlib instrument key，如 600519->sh600519, 688981.SH->sh688981"""
    a = asset.strip().upper()
    # 去掉交易所后缀
    a = re.sub(r"\.(SH|SZ|BJ)$", "", a)
    if a.startswith(("SH", "SZ", "BJ")):
        return a[:2].lower() + a[2:]
    if a.isdigit():
        code = a.zfill(6)
        if code.startswith(("6", "9")):
            return "sh" + code
        if code.startswith(("0", "2", "3")):
            return "sz" + code
        if code.startswith(("4", "8")):
            return "bj" + code
        return "sh" + code
    return a


def read_bin_field(instrument: str, field: str) -> tuple[int, np.ndarray]:
    """读取单个字段的 bin，返回 (起始索引, 数据数组)。不存在则返回 (None, None)"""
    path = FEATURES / instrument / f"{field}.day.bin"
    if not path.exists():
        return None, None
    raw = path.read_bytes()
    arr = np.frombuffer(raw, dtype="<f4")
    if len(arr) < 2:
        return None, None
    return int(arr[0]), arr[1:]


def write_bin_field(instrument: str, field: str, start_idx: int, data: np.ndarray) -> None:
    """写入单个字段的 bin（Qlib 格式：首元素=起始索引 + float32 序列）"""
    out_dir = FEATURES / instrument
    out_dir.mkdir(parents=True, exist_ok=True)
    arr = np.concatenate([np.array([start_idx], dtype="<f4"), np.asarray(data, dtype="<f4")])
    (out_dir / f"{field}.day.bin").write_bytes(arr.tobytes())


def read_instruments() -> list[tuple[str, str, str]]:
    """读取 instruments/all.txt，返回 [(instrument, start_date, end_date)]"""
    if not INSTRUMENTS.exists():
        return []
    out = []
    for line in INSTRUMENTS.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) == 3:
            out.append((parts[0], parts[1], parts[2]))
    return out


def update_instrument(instrument: str, start_date: str, end_date: str) -> None:
    """更新/追加 instruments/all.txt 中的一条记录。"""
    entries = read_instruments()
    new_entry = (instrument, start_date, end_date)
    found = False
    for i, (inst, s, e) in enumerate(entries):
        if inst == instrument:
            # 合并区间
            new_s = min(s, start_date)
            new_e = max(e, end_date)
            entries[i] = (inst, new_s, new_e)
            found = True
            break
    if not found:
        entries.append(new_entry)
    entries.sort(key=lambda x: x[0])
    INSTRUMENTS.write_text(
        "\n".join(f"{i}\t{s}\t{e}" for i, s, e in entries) + "\n",
        encoding="utf-8",
    )


# ──────────────────────────────────────────────────────────────
# 数据拉取：Baostock 优先，akshare 兜底
# ──────────────────────────────────────────────────────────────

_HAS_BAOSTOCK = False
try:
    import baostock as bs
    _HAS_BAOSTOCK = True
except ImportError:
    logger.warning("baostock 未安装，将使用 akshare")

_BS_LOGGED_IN = False


def _bs_login():
    """登录 Baostock（进程内只登一次）"""
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


def to_bs_code(inst: str) -> str:
    """Qlib instrument (sh600519) → Baostock code (sh.600519)"""
    if len(inst) >= 8 and inst[:2] in ("sh", "sz", "bj"):
        return f"{inst[:2]}.{inst[2:]}"
    return inst


def fetch_history_baostock(code: str, start: str, end: str) -> list[dict]:
    """用 Baostock 拉取日线（按股票+区间，免费稳定）"""
    if not _bs_login():
        return []
    bs_code = to_bs_code(code)
    try:
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start, end_date=end,
            frequency="d", adjustflag="2",  # 2=前复权
        )
        rows = []
        while (rs.error_code == "0") and rs.next():
            r = rs.get_row_data()
            if len(r) >= 7:
                rows.append({
                    "date": r[0], "open": _safe(r[1]), "high": _safe(r[2]),
                    "low": _safe(r[3]), "close": _safe(r[4]),
                    "volume": _safe(r[5]), "amount": _safe(r[6]),
                    "change": float("nan"),
                })
        return rows
    except Exception as e:
        logger.warning("baostock fetch %s failed: %s", code, e)
        return []


# 全局 akshare 并发信号量：akshare 易被并发打爆（RemoteDisconnected），限 2 并发
_AKSHARE_SEM = threading.Semaphore(2)


def fetch_history(code: str, start: str = "20000101", end: str = "20261231",
                  max_retries: int = 3) -> list[dict]:
    """拉取单只股票日线。Baostock 优先，akshare 兜底。

    code 接受 qlib instrument 格式（sh600519 / bj430017）。
    返回 [{date, open, high, low, close, volume, amount, ...}]，失败返回空。
    """
    # 北交所 Baostock 不支持，直接走 akshare
    is_bj = code.startswith("bj")
    akshare_code = code[2:] if code[:2] in ("sh", "sz", "bj") else code

    # Baostock 优先（非北交所）
    if _HAS_BAOSTOCK and not is_bj:
        rows = fetch_history_baostock(code, start.replace("-", ""), end.replace("-", ""))
        if rows:
            return rows
        logger.warning("baostock 无数据 %s，尝试 akshare", code)

    # akshare 兜底（含北交所），信号量限并发
    if not _HAS_AKSHARE:
        return []
    for attempt in range(max_retries):
        with _AKSHARE_SEM:
            try:
                df = ak.stock_zh_a_hist(
                    symbol=akshare_code, period="daily",
                    start_date=start.replace("-", ""), end_date=end.replace("-", ""),
                    adjust="qfq",
                )
                if df is None or df.empty:
                    return []
                rows = []
                for _, row in df.iterrows():
                    rows.append({
                        "date": str(row.get("日期", "")),
                        "open": _safe(row.get("开盘")),
                        "high": _safe(row.get("最高")),
                        "low": _safe(row.get("最低")),
                        "close": _safe(row.get("收盘")),
                        "volume": _safe(row.get("成交量")),
                        "amount": _safe(row.get("成交额")),
                        "change": _safe(row.get("涨跌幅")),
                    })
                return rows
            except Exception as e:
                logger.warning("fetch %s attempt %d/%d failed: %s", code, attempt + 1, max_retries, e)
                time.sleep(1.5 * (attempt + 1))  # 退避
    return []


def _safe(v):
    """转 float，失败返回 nan"""
    try:
        f = float(v)
        return f if not np.isnan(f) else float("nan")
    except (ValueError, TypeError):
        return float("nan")


# ──────────────────────────────────────────────────────────────
# 核心同步
# ──────────────────────────────────────────────────────────────

def sync_instrument(asset: str, incremental: bool = False) -> bool:
    """同步单只股票到 qlib_bin。返回是否成功。"""
    inst = instrument_key(asset)
    cal = load_calendar()
    if not cal:
        logger.error("日历缺失: %s", CALENDAR)
        return False

    # 确定起始日期
    start_date = cal[0]
    if incremental:
        # 读已有数据的最后日期
        _, close = read_bin_field(inst, "close")
        if close is not None and len(close) > 0:
            # 起始索引+数据长度-1 = 最后交易日
            si, _ = read_bin_field(inst, "close")
            if si is not None:
                last_idx = si + len(close) - 1
                if last_idx < len(cal) - 1:
                    start_date = cal[last_idx + 1]  # 从下一天开始
                else:
                    logger.info("%s 已是最新", inst)
                    return True

    rows = fetch_history(inst, start=start_date)
    if not rows:
        logger.warning("%s 无数据（实时源不可用）", inst)
        return False

    # 把日期映射到日历索引
    cal_index = {d: i for i, d in enumerate(cal)}
    dated = []
    for r in rows:
        d = r["date"][:10]
        if d in cal_index:
            dated.append((cal_index[d], r))
    if not dated:
        logger.warning("%s 拉取数据不在日历中", inst)
        return False

    dated.sort(key=lambda x: x[0])
    start_idx = dated[0][0]
    n = len(dated)

    # 构造每个字段的序列（无值处填 nan）
    fields_data = {f: np.full(n, np.nan, dtype="<f4") for f in FIELDS}
    for i, (idx, r) in enumerate(dated):
        fields_data["open"][i] = r.get("open", np.nan)
        fields_data["high"][i] = r.get("high", np.nan)
        fields_data["low"][i] = r.get("low", np.nan)
        fields_data["close"][i] = r.get("close", np.nan)
        fields_data["volume"][i] = r.get("volume", np.nan)
        fields_data["amount"][i] = r.get("amount", np.nan)
        fields_data["change"][i] = r.get("change", np.nan) / 100.0 if r.get("change") is not None and not np.isnan(r.get("change", np.nan)) else np.nan
        fields_data["vwap"][i] = (r.get("amount", 0) / r.get("volume", 1)) if r.get("volume") else np.nan

    # 归一化：close 首日=1.0（Qlib 约定）
    first_close = fields_data["close"][0]
    if first_close and not np.isnan(first_close) and first_close != 0:
        for f in ["open", "high", "low", "close", "vwap", "adjclose"]:
            fields_data[f] = fields_data[f] / first_close
        fields_data["adjclose"] = fields_data["close"]  # 归一化后的 adjclose = close
        fields_data["factor"] = np.ones(n, dtype="<f4")
    else:
        fields_data["factor"] = np.ones(n, dtype="<f4")

    # 写入 bin
    for f in FIELDS:
        write_bin_field(inst, f, start_idx, fields_data[f])

    # 更新 instruments
    start_date_str = cal[start_idx]
    end_date_str = cal[start_idx + n - 1]
    update_instrument(inst, start_date_str, end_date_str)

    logger.info("[OK] %s: %s ~ %s (%d 天)", inst, start_date_str, end_date_str, n)
    return True


def main():
    parser = argparse.ArgumentParser(description="Qlib 数据同步（akshare → data/qlib_bin）")
    parser.add_argument("asset", nargs="?", help="股票，如 600519 / sh688981 / 中芯国际")
    parser.add_argument("--incremental", action="store_true", help="增量模式（只拉新日期）")
    parser.add_argument("--batch", type=int, metavar="N", help="批量同步前 N 只（从 all.txt）")
    parser.add_argument("--all", action="store_true", help="全量同步所有 instruments 标的")
    parser.add_argument("--workers", type=int, default=4, help="并发线程数（默认 4）")
    parser.add_argument("--list", help="多只，逗号分隔")
    parser.add_argument("--status", action="store_true", help="查看数据仓库状态")
    parser.add_argument("--update-calendar", action="store_true", help="只更新交易日历，不同步数据")
    args = parser.parse_args()

    # 只更新日历
    if args.update_calendar:
        cal = update_calendar(force=True)
        print(f"日历已更新: {len(cal)} 天, {cal[0]} ~ {cal[-1]}")
        return 0

    if args.status:
        cal = load_calendar()
        insts = read_instruments()
        print(f"日历: {len(cal)} 个交易日 ({cal[0]} ~ {cal[-1]})")
        print(f"instruments: {len(insts)} 条")
        n_feat = sum(1 for d in FEATURES.iterdir() if d.is_dir()) if FEATURES.exists() else 0
        print(f"features 目录: {n_feat} 只")
        # 最近更新的
        latest = sorted(FEATURES.glob("*/close.day.bin"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        for p in latest:
            mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  最近更新: {p.parent.name} ({mtime})")
        return 0

    targets = []
    if args.list:
        targets = [t.strip() for t in args.list.split(",") if t.strip()]
    elif args.all:
        insts = read_instruments()
        targets = [i for i, _, _ in insts]
        logger.info("全量模式：共 %d 只标的", len(targets))
    elif args.batch:
        insts = read_instruments()[:args.batch]
        targets = [i for i, _, _ in insts]
    elif args.asset:
        targets = [args.asset]
    else:
        parser.print_help()
        return 1

    # 批量/全量前先更新日历（让增量能识别新交易日）
    if (args.all or args.batch) and not args.incremental:
        update_calendar(force=True)

    ok = 0
    total = len(targets)
    if total <= 1 or args.workers <= 1:
        # 单线程（单只或显式指定）
        for i, t in enumerate(targets, 1):
            logger.info("同步 %d/%d: %s", i, total, t)
            try:
                if sync_instrument(t, incremental=args.incremental):
                    ok += 1
            except Exception as e:
                logger.error("%s 同步失败: %s", t, e)
            time.sleep(0.5)  # 限流
    else:
        # 并发（批量/全量）
        logger.info("并发 %d 线程同步 %d 只...", args.workers, total)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(sync_instrument, t, args.incremental): t for t in targets}
            done = 0
            for fut in as_completed(futures):
                t = futures[fut]
                done += 1
                try:
                    if fut.result():
                        ok += 1
                except Exception as e:
                    logger.error("%s 同步失败: %s", t, e)
                if done % 50 == 0 or done == total:
                    logger.info("进度: %d/%d", done, total)
                time.sleep(0.1)  # 轻微节流

    print(f"\n[完成] {ok}/{total} 成功")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
