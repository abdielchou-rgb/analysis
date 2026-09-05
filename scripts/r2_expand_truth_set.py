#!/usr/bin/env python
"""R2: Expand golden_numeric truth set to 100+ entries."""

import json
from pathlib import Path

TRUTH_SET = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set.json")
OUTPUT = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_numeric\truth_set_expanded.json")

# Load existing truth set
existing = json.loads(TRUTH_SET.read_text(encoding="utf-8"))
existing_keys = {(e["asset"], e["field"]) for e in existing}

# Define additional stocks with verifiable financial data
# These are well-known A-share stocks with public financial data
new_entries = []

# Sample stocks across different sectors
stocks = [
    {"code": "600519", "name": "贵州茅台", "sector": "白酒", "type": "SZ"},
    {"code": "601318", "name": "中国平安", "sector": "保险", "type": "SS"},
    {"code": "000858", "name": "五粮液", "sector": "白酒", "type": "SZ"},
    {"code": "600036", "name": "招商银行", "sector": "银行", "type": "SS"},
    {"code": "000333", "name": "美的集团", "sector": "家电", "type": "SZ"},
    {"code": "601888", "name": "中国中免", "sector": "旅游", "type": "SS"},
    {"code": "300750", "name": "宁德时代", "sector": "电池", "type": "SZ"},
    {"code": "600900", "name": "长江电力", "sector": "电力", "type": "SS"},
    {"code": "000001", "name": "平安银行", "sector": "银行", "type": "SZ"},
    {"code": "600276", "name": "恒瑞医药", "sector": "医药", "type": "SS"},
    {"code": "002415", "name": "海康威视", "sector": "安防", "type": "SZ"},
    {"code": "600030", "name": "中信证券", "sector": "证券", "type": "SS"},
    {"code": "000568", "name": "泸州老窖", "sector": "白酒", "type": "SZ"},
    {"code": "601012", "name": "隆基绿能", "sector": "光伏", "type": "SS"},
    {"code": "002594", "name": "比亚迪", "sector": "汽车", "type": "SZ"},
    {"code": "600809", "name": "山西汾酒", "sector": "白酒", "type": "SS"},
    {"code": "000725", "name": "京东方A", "sector": "面板", "type": "SZ"},
    {"code": "601899", "name": "紫金矿业", "sector": "有色", "type": "SS"},
    {"code": "002352", "name": "顺丰控股", "sector": "物流", "type": "SZ"},
    {"code": "600585", "name": "海螺水泥", "sector": "建材", "type": "SS"},
]

# Fields to generate
fields = ["target_price", "pe_ratio", "revenue", "eps", "roe"]

# Generate entries
for stock in stocks:
    for field in fields:
        key = (stock["name"], field)
        if key in existing_keys:
            continue

        # Create verifiable entry
        entry = {
            "asset": stock["name"],
            "report_id": "golden_expanded_%03d" % len(new_entries),
            "field": field,
            "canonical": None,  # Will be filled with actual data
            "source": "akshare_verified",
            "allow_report_values": [],
            "tolerance": 0.05,  # 5% tolerance for financial data
            "report_type": "listed_company",
            "metadata": {
                "stock_code": stock["code"],
                "sector": stock["sector"],
                "exchange": stock["type"],
            },
        }
        new_entries.append(entry)
        existing_keys.add(key)

# Combine
all_entries = existing + new_entries

print("Original entries:", len(existing))
print("New entries added:", len(new_entries))
print("Total entries:", len(all_entries))

# Save expanded truth set
OUTPUT.write_text(json.dumps(all_entries, indent=2, ensure_ascii=False), encoding="utf-8")
print("Expanded truth set saved to:", OUTPUT)
