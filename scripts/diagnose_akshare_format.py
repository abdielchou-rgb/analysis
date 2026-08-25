#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实测 akshare stock_financial_abstract_ths 的代码格式（Windows 上跑）

用法: python scripts/diagnose_akshare_format.py
确认深市正确格式后，我再据此修复 sync_akshare_financials.py。
"""

import akshare as ak

test_cases = [
    ("沪市-纯数字", "600519"),
    ("沪市-带SH", "600519.SH"),
    ("深市-纯数字", "000001"),
    ("深市-带SZ", "000001.SZ"),
    ("深市-带sz小写", "000001.sz"),
    ("深市-沪深300格式", "000001.SH"),  # 000001 在 THS 可能被当上证指数
    ("创业板-纯数字", "300750"),
    ("创业板-带SZ", "300750.SZ"),
    ("深市平安-带后缀", "000001.SZ"),
]

print("=== akshare stock_financial_abstract_ths 格式实测 ===\n")
for label, code in test_cases:
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        n = len(df) if df is not None else 0
        marker = "✓" if n > 0 else "✗"
        print(f"  [{marker}] {label} ({code}): {n} 行")
        if n > 0:
            print(f"        列: {list(df.columns)[:6]}")
    except Exception as e:
        print(f"  [✗] {label} ({code}): {str(e)[:60]}")

print("\n结论：能返回>0行的格式就是对的。")
