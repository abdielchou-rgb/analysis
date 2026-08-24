# -*- coding: utf-8 -*-
"""
R53 P2-2：美国高频指标 → data/us_highfreq.json
CFNAI（芝加哥联储全国活动指数，月频）、WEI（纽约联储周度经济指数，周频）、
5y5y 盈亏平衡通胀率（FRED T5YIFR；缺失时用 T10YIE 近似）。
数据源：FRED fredgraph.csv 免 key 端点（https://fred.stlouisfed.org/graph/fredgraph.csv?id=XXX）
"""
from __future__ import annotations

import json
import os
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "us_highfreq.json")
BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _fetch(series_id: str, max_tries: int = 6) -> str:
    last = None
    for i in range(max_tries):
        try:
            r = requests.get(BASE.format(series_id), headers=HEADERS, timeout=(10, 40))
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (2 ** i))
    raise last


def _parse_csv(text: str) -> list[dict]:
    lines = text.strip().splitlines()
    if not lines:
        return []
    header = lines[0].split(",")
    if len(header) < 2:
        return []
    name = header[1].strip()
    out = []
    for ln in lines[1:]:
        parts = ln.split(",")
        if len(parts) < 2:
            continue
        d, v = parts[0].strip(), parts[1].strip()
        if not d or v in ("", "."):
            continue
        try:
            out.append({"date": d, "value": float(v)})
        except ValueError:
            continue
    return {"series": name, "data": out, "count": len(out), "source": "FRED fredgraph.csv (免key端点)"}


def main():
    result = {}
    for sid in ["CFNAI", "WEI", "T5YIFR", "T10YIE"]:
        try:
            text = _fetch(sid)
            parsed = _parse_csv(text)
            if parsed["count"] > 0:
                result[sid] = parsed
                print(f"[OK] {sid}: {parsed['count']} 期")
            else:
                result[sid] = {"series": sid, "data": [], "count": 0, "source": "unavailable: 空数据"}
                print(f"[FAIL] {sid}: 空")
        except Exception as e:  # noqa: BLE001
            result[sid] = {"series": sid, "data": [], "count": 0, "source": "unavailable", "reason": str(e)[:200]}
            print(f"[FAIL] {sid}: {str(e)[:120]}")
        time.sleep(0.6)
    # 5y5y 近似：T5YIFR 缺失 → T10YIE 注明
    if result.get("T5YIFR", {}).get("count", 0) == 0 and result.get("T10YIE", {}).get("count", 0) > 0:
        result["5y5y_盈亏平衡通胀率"] = {
            "series": "5y5y breakeven (近似 T10YIE)",
            "data": result["T10YIE"]["data"],
            "count": result["T10YIE"]["count"],
            "source": "FRED T10YIE (10Y breakeven，近似 5y5y)",
        }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"[DONE] 写入 {OUT}")


if __name__ == "__main__":
    main()
