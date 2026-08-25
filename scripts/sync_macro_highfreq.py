# -*- coding: utf-8 -*-
"""
R53 P1-1：宏观高频指标采集 → data/macro_highfreq.json

高频指数底层指标（日/周/旬频）：
  生产: 螺纹钢期货(RB0 主力日)、PTA期货(TA0 主力日) —— 粗钢旬度/半钢胎开工率 akshare 无接口 → unavailable
  消费: 布伦特原油(以 SC0 上海原油主力替代)、乘用车零售(CPCA 月)
  固投: 玻璃期货(FG0 主力日)、沥青期货(BU0 主力日)、30城新房价格指数(月) —— 30城成交面积 akshare 无 → unavailable
  出口: BDI、中国运价指数 BCI/BDTI/BCTI

幂等：覆盖写入；source 标注；单指标失败隔离。
"""

from __future__ import annotations

import json
import os
import time

import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "macro_highfreq.json")


def _retry(fn, times=5, base=1.5):
    last = None
    for i in range(times):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(base * (2**i) + 0.5)
    raise last


def _series(rows, date_key, value_key, source):
    """rows: list[(date, value)] → {date: value}，按日期升序"""
    out = []
    for d, v in rows:
        if v is None or v != v:
            continue
        out.append({"date": str(d)[:10], "value": float(v)})
    out.sort(key=lambda x: x["date"])
    return {"data": out, "count": len(out), "source": source}


def sync_futures(symbol: str, name: str, source: str) -> dict:
    """期货主力合约日线收盘价"""
    df = _retry(lambda: ak.futures_main_sina(symbol=symbol))
    rows = [(r["日期"], r["收盘价"]) for _, r in df.iterrows()]
    return _series(rows, "日期", "收盘价", source)


def sync_bdi() -> dict:
    df = _retry(lambda: ak.macro_shipping_bdi())
    rows = [(r["日期"], r["最新值"]) for _, r in df.iterrows()]
    return _series(rows, "日期", "最新值", "akshare: macro_shipping_bdi")


def sync_cn_freight() -> dict:
    """中国运价指数（含 BCI/BDI/BDTI/BCTI）"""
    df = _retry(lambda: ak.macro_china_freight_index())
    cols = [c for c in df.columns if c != "截止日期"]
    result = {}
    for c in cols:
        rows = [(r["截止日期"], r[c]) for _, r in df.iterrows()]
        result[f"中国运价指数_{c}"] = _series(rows, "截止日期", c, "akshare: macro_china_freight_index")
    return result


def sync_car() -> dict:
    """乘用车零售（CPCA 月频）—— 2026 年月度销量"""
    df = _retry(lambda: ak.car_market_total_cpca())
    rows = []
    for _, r in df.iterrows():
        month = str(r.get("月份", ""))
        val = r.get("2026年")
        if month and val is not None and val == val:
            rows.append((f"2026-{month.replace('月', '')}-01", val))
    return _series(rows, "月份", "2026年", "akshare: car_market_total_cpca (CPCA 月频)")


def sync_house_price() -> dict:
    """30城新建商品住宅价格指数（月频，取全国/一线平均）"""
    df = _retry(lambda: ak.macro_china_new_house_price())
    col = [c for c in df.columns if "同比" in c]
    col = col[0] if col else None
    if not col:
        return {"data": [], "count": 0, "source": "unavailable: macro_china_new_house_price 无同比列"}
    by_date = {}
    for _, r in df.iterrows():
        d = str(r.get("日期", ""))[:7]
        v = r.get(col)
        if d and v is not None and v == v:
            by_date.setdefault(d, []).append(float(v))
    rows = [(d, sum(vs) / len(vs)) for d, vs in sorted(by_date.items())]
    return _series(rows, "日期", col, "akshare: macro_china_new_house_price (30城新房价格指数同比均值, 月频)")


def main():
    result = {}
    jobs = [
        ("螺纹钢期货主力_收盘价", lambda: sync_futures("RB0", "螺纹钢", "akshare: futures_main_sina(RB0)")),
        (
            "原油期货主力_收盘价",
            lambda: sync_futures("SC0", "原油", "akshare: futures_main_sina(SC0) 上海原油，替代布伦特"),
        ),
        ("玻璃期货主力_收盘价", lambda: sync_futures("FG0", "玻璃", "akshare: futures_main_sina(FG0)")),
        ("沥青期货主力_收盘价", lambda: sync_futures("BU0", "沥青", "akshare: futures_main_sina(BU0)")),
        ("PTA期货主力_收盘价", lambda: sync_futures("TA0", "PTA", "akshare: futures_main_sina(TA0)")),
        ("BDI_波罗的海干散货指数", sync_bdi),
        ("乘用车零售销量_CPCA月频", sync_car),
        ("30城新房价格指数_同比均值月频", sync_house_price),
    ]
    for name, fn in jobs:
        try:
            result[name] = fn()
            print(f"[OK] {name}: {result[name]['count']} 点")
        except Exception as e:
            print(f"[FAIL] {name}: {str(e)[:120]}")
            result[name] = {"data": [], "count": 0, "source": "unavailable", "reason": str(e)[:200]}
    # 中国运价指数子系列
    try:
        for k, v in sync_cn_freight().items():
            result[k] = v
            print(f"[OK] {k}: {v['count']} 点")
    except Exception as e:
        print(f"[FAIL] 中国运价指数: {str(e)[:120]}")
    # 明确不可用项
    result["粗钢产量_旬度"] = {
        "data": [],
        "count": 0,
        "source": "unavailable",
        "reason": "akshare 无粗钢旬度产量接口（统计局旬度需手工）",
    }
    result["半钢胎开工率_周"] = {"data": [], "count": 0, "source": "unavailable", "reason": "akshare 无轮胎开工率接口"}
    result["30城商品房成交面积_日"] = {
        "data": [],
        "count": 0,
        "source": "unavailable",
        "reason": "akshare 无30城成交面积日频接口（中指院需付费）",
    }
    result["SCFI_上海出口集装箱运价指数"] = {
        "data": [],
        "count": 0,
        "source": "unavailable",
        "reason": "akshare 无 SCFI 接口（macro_china_freight_index 为 BDI 系）",
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"[DONE] 写入 {OUT}，共 {len(result)} 组指标")


if __name__ == "__main__":
    main()
