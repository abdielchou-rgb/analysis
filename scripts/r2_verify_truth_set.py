#!/usr/bin/env python
"""R2: Fill golden_numeric with real financial data from akshare."""

import json
from pathlib import Path

try:
    import akshare as ak

    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    print("WARNING: akshare not installed, using placeholder values")

TRUTH_SET = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set_expanded.json")
OUTPUT = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set_verified.json")

# Load truth set
entries = json.loads(TRUTH_SET.read_text(encoding="utf-8"))

# Stock code mapping
stock_codes = {
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

# Fetch real data if akshare is available
verified_count = 0
for entry in entries:
    if entry.get("source") == "akshare_verified" and entry["canonical"] is None:
        asset = entry["asset"]
        field = entry["field"]
        code = stock_codes.get(asset, entry.get("metadata", {}).get("stock_code"))

        if code and HAS_AKSHARE:
            try:
                # Fetch real-time quote
                df = ak.stock_zh_a_spot_em()
                stock_row = df[df["代码"] == code]

                if not stock_row.empty:
                    row = stock_row.iloc[0]

                    if field == "target_price":
                        # Use current price as baseline
                        entry["canonical"] = float(row.get("最新价", 0))
                    elif field == "pe_ratio":
                        entry["canonical"] = float(row.get("市盈率-动态", 0))
                    elif field == "eps":
                        entry["canonical"] = float(row.get("每股收益", 0)) if row.get("每股收益") else None
                    elif field == "roe":
                        entry["canonical"] = None  # Not available in spot data
                    elif field == "revenue":
                        entry["canonical"] = None  # Not available in spot data

                    if entry["canonical"] is not None:
                        entry["allow_report_values"] = [entry["canonical"]]
                        entry["source"] = "akshare_realtime"
                        verified_count += 1

            except Exception as e:
                print("Error fetching %s: %s" % (asset, e))

print("Verified %d entries with real data" % verified_count)
print("Remaining %d entries need manual verification" % sum(1 for e in entries if e["canonical"] is None))

# Save verified truth set
OUTPUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
print("Verified truth set saved to:", OUTPUT)
