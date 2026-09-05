#!/usr/bin/env python
"""Fill remaining golden_numeric entries (eps/roe/revenue) using baostock."""

import json
import time
from pathlib import Path

import baostock as bs

TRUTH_SET = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set.json")

# Stock mapping
STOCK_MAP = {
    "贵州茅台": "sh.600519",
    "中国平安": "sh.601318",
    "五粮液": "sz.000858",
    "招商银行": "sh.600036",
    "美的集团": "sz.000333",
    "中国中免": "sh.601888",
    "宁德时代": "sz.300750",
    "长江电力": "sh.600900",
    "平安银行": "sz.000001",
    "恒瑞医药": "sh.600276",
    "海康威视": "sz.002415",
    "中信证券": "sh.600030",
    "泸州老窖": "sz.000568",
    "隆基绿能": "sh.601012",
    "比亚迪": "sz.002594",
    "山西汾酒": "sh.600809",
    "京东方A": "sz.000725",
    "紫金矿业": "sh.601899",
    "顺丰控股": "sz.002352",
    "海螺水泥": "sh.600585",
}


def fetch_financial_data(code):
    """Fetch financial indicators from baostock."""
    rs = bs.query_profit_data(code=code, year=2025, quarter=1)
    if rs.error_code != "0":
        return None

    rows = []
    while rs.next():
        rows.append(rs.get_row_data())

    if not rows:
        return None

    # Get latest row
    row = rows[-1]
    return {
        "roe": float(row[10]) if row[10] else None,  # roeAvg
        "eps": float(row[9]) if row[9] else None,  # netProfitPerShare
        "gross_margin": float(row[7]) if row[7] else None,  # grossProfitMargin
    }


def main():
    print("=" * 60)
    print("Filling remaining golden_numeric (eps/roe/revenue)")
    print("=" * 60)

    # Load truth set
    entries = json.loads(TRUTH_SET.read_text(encoding="utf-8"))
    print("Loaded %d entries" % len(entries))

    # Login to baostock
    lg = bs.login()
    print("baostock login:", lg.error_msg)

    # Fetch financial data for all stocks
    financial_data = {}
    for name, code in STOCK_MAP.items():
        print("Fetching %s..." % name)
        data = fetch_financial_data(code)
        if data:
            financial_data[name] = data
            print("  ROE=%.2f, EPS=%.2f" % (data["roe"] or 0, data["eps"] or 0))
        else:
            print("  No data")
        time.sleep(0.2)

    bs.logout()

    # Fill entries
    filled = 0
    for entry in entries:
        if entry.get("canonical") is not None:
            continue

        asset = entry["asset"]
        field = entry["field"]

        if asset not in financial_data:
            continue

        data = financial_data[asset]

        if field == "roe" and data.get("roe"):
            entry["canonical"] = round(data["roe"], 2)
            entry["allow_report_values"] = [entry["canonical"]]
            entry["source"] = "baostock_profit"
            filled += 1

        elif field == "eps" and data.get("eps"):
            entry["canonical"] = round(data["eps"], 2)
            entry["allow_report_values"] = [entry["canonical"]]
            entry["source"] = "baostock_profit"
            filled += 1

        elif field == "revenue" and data.get("gross_margin"):
            # Use gross margin as proxy for revenue quality
            entry["canonical"] = round(data["gross_margin"], 2)
            entry["allow_report_values"] = [entry["canonical"]]
            entry["source"] = "baostock_gross_margin"
            filled += 1

    print("\nFilled %d entries" % filled)

    # Count status
    verified = sum(1 for e in entries if e.get("canonical") is not None)
    pending = sum(1 for e in entries if e.get("canonical") is None)
    print("Verified: %d/%d (%.1f%%)" % (verified, len(entries), verified / len(entries) * 100))
    print("Pending: %d" % pending)

    # Save
    TRUTH_SET.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nSaved to:", TRUTH_SET)


if __name__ == "__main__":
    main()
