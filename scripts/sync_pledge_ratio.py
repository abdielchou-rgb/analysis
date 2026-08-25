# -*- coding: utf-8 -*-
"""
R53 P1-2：大股东质押率 → data/pledge_ratio.json
数据源：akshare stock_gpzy_pledge_ratio_detail_em（东财股权质押明细，全市场一次性拉取）
pledgeRatio 定义：每股最新公告日期的 max(占所持股份比例)（股东层面质押率上限）
"""

from __future__ import annotations

import json
import os

import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "pledge_ratio.json")


def main():
    df = ak.stock_gpzy_pledge_ratio_detail_em()
    print("rows", len(df), flush=True)
    # 列名（GBK 乱码风险，用位置/关键词定位）
    cols = list(df.columns)
    print("cols", cols, flush=True)
    # 中文列名在此环境乱码，但结构固定；用索引定位关键列
    # 预期顺序：序号/股票代码/股票简称/股东名称/质押股份数量/占所持股份比例/占总股本比例/质押机构/最新价/质押日收盘价/预计平仓线/质押开始日期/质押结束日期/状态/公告日期
    code_col = df.columns[1]
    ratio_col = df.columns[5]  # 占所持股份比例
    date_col = df.columns[-1]  # 公告日期
    name_col = df.columns[3]

    best = {}
    for _, r in df.iterrows():
        code = str(r[code_col]).zfill(6)
        try:
            ratio = float(r[ratio_col])
        except (TypeError, ValueError):
            continue
        try:
            if isinstance(r[date_col], str) and r[date_col].strip():
                # '2026-06-30' / '2026/6/30' 字符串日期
                d = int(r[date_col].replace("-", "").replace("/", "")[:8])
            else:
                d = int(r[date_col])  # 毫秒时间戳
        except (TypeError, ValueError):
            d = 0
        cur = best.get(code)
        if cur is None or d > cur["date"]:
            best[code] = {"code": code, "pledgeRatio": round(ratio, 2), "date": d}
        elif d == cur["date"] and ratio > cur["pledgeRatio"]:
            cur["pledgeRatio"] = round(ratio, 2)

    out = []
    for code, info in best.items():
        if info["pledgeRatio"] < 0 or info["pledgeRatio"] > 100:
            continue
        out.append(
            {
                "code": code,
                "pledgeRatio": info["pledgeRatio"],
                "announceDate": info["date"],
                "source": "akshare: stock_gpzy_pledge_ratio_detail_em",
            }
        )
    out.sort(key=lambda x: x["code"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("DONE", len(out), "只", flush=True)
    # 抽查
    for c in ["600519", "002169", "600381"]:
        hit = [x for x in out if x["code"] == c]
        print(c, hit[:1], flush=True)


if __name__ == "__main__":
    main()
