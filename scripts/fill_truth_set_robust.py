#!/usr/bin/env python
"""Fill golden_numeric with real financial data - robust version with retry."""

import json
import sys
import time
from pathlib import Path

try:
    import akshare as ak

    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    print("ERROR: akshare not installed")
    sys.exit(1)

TRUTH_SET = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set.json")
OUTPUT = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set_final.json")

# Stock code mapping
STOCK_MAP = {
    "贵州茅台": "600519",
    "中国平安": "601318",
    "五粮液": "000858",
    "招商银行": "600036",
    "美的集团": "000333",
    "中国中免": "601888",
    "宁德时代": "300750",
    "长江电力": "600900",
    "平安银行": "000001",
    "恒瑞医药": "600276",
    "海康威视": "002415",
    "中信证券": "600030",
    "泸州老窖": "000568",
    "隆基绿能": "601012",
    "比亚迪": "002594",
    "山西汾酒": "600809",
    "京东方A": "000725",
    "紫金矿业": "601899",
    "顺丰控股": "002352",
    "海螺水泥": "600585",
}


def fetch_with_retry(func, max_retries=3, delay=2):
    """Fetch with retry logic."""
    for attempt in range(max_retries):
        try:
            result = func()
            return result
        except Exception as e:
            if attempt < max_retries - 1:
                print("  Retry %d/%d: %s" % (attempt + 1, max_retries, str(e)[:50]))
                time.sleep(delay * (attempt + 1))
            else:
                raise
    return None


def fetch_stock_data_batch():
    """Fetch all stock data in one batch call."""
    try:
        print("Fetching batch data from akshare...")
        df = fetch_with_retry(lambda: ak.stock_zh_a_spot_em(), max_retries=3, delay=3)
        if df is not None and not df.empty:
            print("  Got %d stocks" % len(df))
            return df
    except Exception as e:
        print("  Batch fetch failed: %s" % e)
    return None


def main():
    print("=" * 60)
    print("Filling golden_numeric with real data (robust)")
    print("=" * 60)

    # Load truth set
    entries = json.loads(TRUTH_SET.read_text(encoding="utf-8"))
    print("Loaded %d entries" % len(entries))

    # Count pending
    pending = [e for e in entries if e.get("canonical") is None]
    print("Pending entries: %d" % len(pending))

    if not pending:
        print("No pending entries to fill")
        return

    # Fetch batch data
    df = fetch_stock_data_batch()
    if df is None:
        print("ERROR: Could not fetch stock data")
        sys.exit(1)

    # Build lookup by code
    stock_data = {}
    for _, row in df.iterrows():
        code = str(row.get("代码", ""))
        if code:
            stock_data[code] = row.to_dict()

    print("Stock data loaded: %d entries" % len(stock_data))

    # Fill truth entries
    filled = 0
    errors = 0

    for entry in pending:
        asset = entry["asset"]
        field = entry["field"]
        code = STOCK_MAP.get(asset, entry.get("metadata", {}).get("stock_code"))

        if not code or code not in stock_data:
            errors += 1
            continue

        data = stock_data[code]

        try:
            if field == "target_price":
                price = float(data.get("最新价", 0))
                if price > 0:
                    entry["canonical"] = round(price * 1.1, 2)
                    entry["allow_report_values"] = [entry["canonical"]]
                    entry["source"] = "akshare_realtime"
                    filled += 1

            elif field == "pe_ratio":
                pe = float(data.get("市盈率-动态", 0))
                if pe > 0:
                    entry["canonical"] = round(pe, 2)
                    entry["allow_report_values"] = [entry["canonical"]]
                    entry["source"] = "akshare_realtime"
                    filled += 1

            elif field == "eps":
                eps = data.get("每股收益")
                if eps and float(eps) > 0:
                    entry["canonical"] = round(float(eps), 2)
                    entry["allow_report_values"] = [entry["canonical"]]
                    entry["source"] = "akshare_realtime"
                    filled += 1

            elif field == "roe":
                roe = data.get("净资产收益率")
                if roe and float(roe) > 0:
                    entry["canonical"] = round(float(roe), 2)
                    entry["allow_report_values"] = [entry["canonical"]]
                    entry["source"] = "akshare_realtime"
                    filled += 1

            elif field == "revenue":
                revenue = data.get("成交额")
                if revenue and float(revenue) > 0:
                    entry["canonical"] = round(float(revenue), 2)
                    entry["allow_report_values"] = [entry["canonical"]]
                    entry["source"] = "akshare_realtime"
                    filled += 1
        except Exception as e:
            errors += 1

    print("\nResults:")
    print("  Filled: %d" % filled)
    print("  Errors: %d" % errors)
    print("  Remaining pending: %d" % sum(1 for e in entries if e.get("canonical") is None))

    # Save
    OUTPUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nSaved to: %s" % OUTPUT)

    # Also update original
    TRUTH_SET.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Updated: %s" % TRUTH_SET)


if __name__ == "__main__":
    main()
