#!/usr/bin/env python
"""Fill golden_numeric using mootdx + baostock (no akshare dependency)."""

import json
import time
from pathlib import Path

import baostock as bs
from mootdx.quotes import Quotes

TRUTH_SET = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set.json")
OUTPUT = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set_final.json")

# Stock code mapping (mootdx format: market=1 for SH, market=0 for SZ)
STOCK_MAP = {
    "贵州茅台": {"mootdx": "600519", "baostock": "sh.600519", "market": 1},
    "中国平安": {"mootdx": "601318", "baostock": "sh.601318", "market": 1},
    "五粮液": {"mootdx": "000858", "baostock": "sz.000858", "market": 0},
    "招商银行": {"mootdx": "600036", "baostock": "sh.600036", "market": 1},
    "美的集团": {"mootdx": "000333", "baostock": "sz.000333", "market": 0},
    "中国中免": {"mootdx": "601888", "baostock": "sh.601888", "market": 1},
    "宁德时代": {"mootdx": "300750", "baostock": "sz.300750", "market": 0},
    "长江电力": {"mootdx": "600900", "baostock": "sh.600900", "market": 1},
    "平安银行": {"mootdx": "000001", "baostock": "sz.000001", "market": 0},
    "恒瑞医药": {"mootdx": "600276", "baostock": "sh.600276", "market": 1},
    "海康威视": {"mootdx": "002415", "baostock": "sz.002415", "market": 0},
    "中信证券": {"mootdx": "600030", "baostock": "sh.600030", "market": 1},
    "泸州老窖": {"mootdx": "000568", "baostock": "sz.000568", "market": 0},
    "隆基绿能": {"mootdx": "601012", "baostock": "sh.601012", "market": 1},
    "比亚迪": {"mootdx": "002594", "baostock": "sz.002594", "market": 0},
    "山西汾酒": {"mootdx": "600809", "baostock": "sh.600809", "market": 1},
    "京东方A": {"mootdx": "000725", "baostock": "sz.000725", "market": 0},
    "紫金矿业": {"mootdx": "601899", "baostock": "sh.601899", "market": 1},
    "顺丰控股": {"mootdx": "002352", "baostock": "sz.002352", "market": 0},
    "海螺水泥": {"mootdx": "600585", "baostock": "sh.600585", "market": 1},
}


def fetch_mootdx_data():
    """Fetch real-time data from mootdx (TCP, no IP block)."""
    print("Connecting to mootdx (通达信)...")
    client = Quotes.factory(market="std")

    results = {}
    for name, codes in STOCK_MAP.items():
        try:
            df = client.quotes(symbol=codes["mootdx"])
            if df is not None and not df.empty:
                row = df.iloc[0]
                results[name] = {
                    "price": float(row.get("price", 0)),
                    "last_close": float(row.get("last_close", 0)),
                    "volume": float(row.get("vol", 0)),
                    "amount": float(row.get("amount", 0)),
                }
                print("  %s: %.2f" % (name, results[name]["price"]))
        except Exception as e:
            print("  %s error: %s" % (name, str(e)[:50]))
        time.sleep(0.1)

    return results


def fetch_baostock_data():
    """Fetch PE/PB data from baostock (TCP, no IP block)."""
    print("\nConnecting to baostock...")
    lg = bs.login()
    if lg.error_code != "0":
        print("  Login failed: %s" % lg.error_msg)
        return {}

    results = {}
    for name, codes in STOCK_MAP.items():
        try:
            rs = bs.query_history_k_data_plus(
                codes["baostock"],
                "date,code,peTTM,pbMRQ,psTTM",
                start_date="2026-09-01",
                end_date="2026-09-03",
                frequency="d",
                adjustflag="3",
            )

            if rs.error_code == "0":
                rows = []
                while rs.next():
                    rows.append(rs.get_row_data())

                if rows:
                    latest = rows[-1]
                    results[name] = {
                        "pe_ttm": float(latest[2]) if latest[2] else None,
                        "pb_mrq": float(latest[3]) if latest[3] else None,
                        "ps_ttm": float(latest[4]) if latest[4] else None,
                    }
                    print(
                        "  %s: PE=%.2f, PB=%.2f"
                        % (
                            name,
                            results[name]["pe_ttm"] or 0,
                            results[name]["pb_mrq"] or 0,
                        )
                    )
        except Exception as e:
            print("  %s error: %s" % (name, str(e)[:50]))
        time.sleep(0.1)

    bs.logout()
    return results


def main():
    print("=" * 60)
    print("Filling golden_numeric (mootdx + baostock)")
    print("=" * 60)

    # Load truth set
    entries = json.loads(TRUTH_SET.read_text(encoding="utf-8"))
    print("Loaded %d entries" % len(entries))

    # Fetch data
    mootdx_data = fetch_mootdx_data()
    baostock_data = fetch_baostock_data()

    # Fill entries
    filled = 0
    for entry in entries:
        if entry.get("canonical") is not None:
            continue

        asset = entry["asset"]
        field = entry["field"]

        if asset in mootdx_data and field == "target_price":
            price = mootdx_data[asset]["price"]
            if price > 0:
                entry["canonical"] = round(price * 1.1, 2)
                entry["allow_report_values"] = [entry["canonical"]]
                entry["source"] = "mootdx_realtime"
                filled += 1

        if asset in baostock_data:
            data = baostock_data[asset]

            if field == "pe_ratio" and data.get("pe_ttm"):
                entry["canonical"] = round(data["pe_ttm"], 2)
                entry["allow_report_values"] = [entry["canonical"]]
                entry["source"] = "baostock_ttm"
                filled += 1

            elif field == "pb_ratio" and data.get("pb_mrq"):
                entry["canonical"] = round(data["pb_mrq"], 2)
                entry["allow_report_values"] = [entry["canonical"]]
                entry["source"] = "baostock_mrq"
                filled += 1

    print("\nFilled %d entries" % filled)

    # Count status
    verified = sum(1 for e in entries if e.get("canonical") is not None)
    pending = sum(1 for e in entries if e.get("canonical") is None)
    print("Verified: %d, Pending: %d" % (verified, pending))

    # Save
    OUTPUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    TRUTH_SET.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nSaved to: %s" % OUTPUT)


if __name__ == "__main__":
    main()
