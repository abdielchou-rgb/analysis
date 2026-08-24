#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断创业板 300xxx 在同花顺接口失败的原因

300750 诊断时成功，但全量时 300001 起全失败。
本脚本对比多个创业板代码 + 多个 akshare 接口，定位问题。

用法: python scripts/diagnose_cyb.py
"""
import akshare as ak
import traceback

# 测试：同花顺接口对多个创业板代码
ths_codes = ["300001", "300003", "300750", "300059", "301236", "300999"]
print("=== 1. 同花顺 stock_financial_abstract_ths（当前用的接口）===")
for code in ths_codes:
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        n = len(df) if df is not None else 0
        cols = list(df.columns)[:8] if n else []
        print(f"  [{'✓' if n>0 else '✗'}] {code}: {n} 行, 列={cols}")
        if n == 0 and df is not None:
            print(f"        空 DataFrame，但无异常")
    except Exception as e:
        print(f"  [✗] {code}: {type(e).__name__}: {str(e)[:80]}")

print("\n=== 2. 同花顺按年度接口（indicator=按年度）===")
for code in ths_codes[:3]:
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
        n = len(df) if df is not None else 0
        print(f"  [{'✓' if n>0 else '✗'}] {code}: {n} 行")
    except Exception as e:
        print(f"  [✗] {code}: {type(e).__name__}: {str(e)[:80]}")

print("\n=== 3. 新浪源 stock_financial_abstract（替代接口）===")
for code in ths_codes[:3]:
    try:
        df = ak.stock_financial_abstract(symbol=code)
        n = len(df) if df is not None else 0
        cols = list(df.columns)[:8] if n else []
        print(f"  [{'✓' if n>0 else '✗'}] {code}: {n} 行, 列={cols}")
        if n:
            # 打印最新一行的关键字段
            last = df.iloc[-1]
            print(f"        最新: {dict(last.head(6))}")
    except Exception as e:
        print(f"  [✗] {code}: {type(e).__name__}: {str(e)[:80]}")

print("\n=== 4. 深市主板对照（确认不是所有深市都挂）===")
for code in ["000001", "000002", "002594"]:
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        n = len(df) if df is not None else 0
        print(f"  [{'✓' if n>0 else '✗'}] {code}: {n} 行")
    except Exception as e:
        print(f"  [✗] {code}: {type(e).__name__}: {str(e)[:80]}")

print("\n结论：看哪些接口能返回>0行，那个接口就是创业板兜底源。")
