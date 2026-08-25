# -*- coding: utf-8 -*-
"""
R53 P2-1：领先指标库 → data/leading_indicators.json
采集宏观领先关系指标：
- M1-M2 剪刀差（央行，月度）: akshare macro_china_money_supply
- 信贷脉冲（社融增量 12 个月滚动同比）: akshare macro_china_shrzgm
- 专项债发行（财政部，人工维护最新值）
- 能繁母猪存栏（农业农村部/统计局，人工维护最新值）
- 土地成交总价（无免费接口，标记 unavailable）
"""

from __future__ import annotations

import json
import os

import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "leading_indicators.json")


def _norm_date(s):
    s = str(s)
    # '2008年03月份' -> '2008-03'；'202604' -> '2026-04'
    if "年" in s:
        y = s.split("年")[0]
        m = s.split("年")[1].replace("月份", "").replace("月", "")
        return f"{y}-{int(m):02d}"
    if len(s) == 6 and s.isdigit():
        return f"{s[:4]}-{s[4:]}"
    return s


def build_m1_m2():
    df = ak.macro_china_money_supply()
    rows = []
    for _, r in df.iterrows():
        d = _norm_date(r["月份"])
        m1 = r.get("货币(M1)-同比增长")
        m2 = r.get("货币和准货币(M2)-同比增长")
        if m1 is None or m2 is None:
            continue
        try:
            m1v, m2v = float(m1), float(m2)
        except (TypeError, ValueError):
            continue
        rows.append({"date": d, "value": round(m1v - m2v, 2)})
    rows.sort(key=lambda x: x["date"])
    return rows, "akshare: macro_china_money_supply"


def build_credit_pulse():
    df = ak.macro_china_shrzgm()
    rows = []
    for _, r in df.iterrows():
        d = _norm_date(r["月份"])
        v = r.get("社会融资规模增量")
        if v is None:
            continue
        try:
            rows.append({"date": d, "value": float(v)})
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda x: x["date"])
    # 12 个月滚动求和 → 同比
    n = 12
    pulse = []
    for i in range(n - 1, len(rows)):
        cur12 = sum(x["value"] for x in rows[i - n + 1 : i + 1])
        if i >= n * 2 - 1:
            prev12 = sum(x["value"] for x in rows[i - n * 2 + 1 : i - n + 1])
            if prev12 != 0:
                pulse.append({"date": rows[i]["date"], "value": round((cur12 - prev12) / prev12 * 100, 2)})
    return pulse, "akshare: macro_china_shrzgm (社融增量12月滚动同比)"


def build_manual():
    return [
        {
            "指标": "专项债发行",
            "latest_value": 5716,
            "latest_date": "2026-06",
            "source": "财政部 2026年6月地方政府债券发行和债务余额情况 (2026-07-27)",
            "note": "6月单月新增专项债 5716 亿元；1-6 月累计 20667 亿元",
            "history": [],
        },
        {
            "指标": "能繁母猪存栏",
            "latest_value": 3780,
            "latest_date": "2026-06",
            "source": "国家统计局/农业农村部 2026年上半年农业农村经济运行情况 (2026-07-24)",
            "note": "二季度末 3780 万头，同比 -263 万头 (-6.5%)；正常保有量 3750 万头，处于绿色区间",
            "history": [],
        },
    ]


def main():
    result = {}
    m1m2, src1 = build_m1_m2()
    result["M1-M2剪刀差"] = {
        "latest_value": m1m2[-1]["value"] if m1m2 else None,
        "latest_date": m1m2[-1]["date"] if m1m2 else None,
        "source": src1,
        "history": m1m2,
    }
    print(f"[OK] M1-M2剪刀差: {len(m1m2)} 期, latest={m1m2[-1] if m1m2 else None}")

    pulse, src2 = build_credit_pulse()
    result["信贷脉冲"] = {
        "latest_value": pulse[-1]["value"] if pulse else None,
        "latest_date": pulse[-1]["date"] if pulse else None,
        "source": src2,
        "history": pulse,
    }
    print(f"[OK] 信贷脉冲: {len(pulse)} 期, latest={pulse[-1] if pulse else None}")

    for m in build_manual():
        name = m.pop("指标")
        result[name] = m
        print(f"[OK] {name}: {m['latest_value']} @ {m['latest_date']}")

    result["土地成交总价"] = {
        "latest_value": None,
        "latest_date": None,
        "source": "unavailable: 无免费接口(中指院/统计局需付费)",
        "history": [],
    }
    print("[FAIL] 土地成交总价: 无免费接口，标记 unavailable")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"[DONE] 写入 {OUT}")


if __name__ == "__main__":
    main()
