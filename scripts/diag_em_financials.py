#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断 akshare 东财三表接口（在用户主机跑，定位深市 balance 不写入的根因）

用法:
    python scripts/diag_em_financials.py 000001     # 单只诊断
    python scripts/diag_em_financials.py 300750
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import akshare as ak  # 用户机应已安装


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "000001"
    print(f"=== 诊断东财三表接口: {code} ===")

    # 1. THS 摘要（profit 来源）
    print("\n--- 1. 同花顺摘要 stock_financial_abstract_ths ---")
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is None or df.empty:
            print("  空")
        else:
            print(f"  行数: {len(df)}, 列: {list(df.columns)[:12]}")
            print(f"  最新报告期: {df.iloc[0].get('报告期')}")
    except Exception as e:
        print(f"  失败: {type(e).__name__}: {str(e)[:150]}")

    # 2. 东财资产负债表
    print("\n--- 2. 东财资产负债表 stock_balance_sheet_by_report_em ---")
    try:
        bs = ak.stock_balance_sheet_by_report_em(symbol=code)
        if bs is None or bs.empty:
            print("  空（这是问题所在）")
        else:
            print(f"  行数: {len(bs)}")
            print(f"  列名(前20): {list(bs.columns)[:20]}")
            if len(bs) > 0:
                row = bs.iloc[0]
                print(f"  最新报告期: {row.get('REPORT_DATE')}")
                # 检查列名大小写
                cols_lower = {str(c).lower() for c in bs.columns}
                print(f"  含 total_assets: {'total_assets' in cols_lower}")
                print(f"  含 TOTAL_ASSETS: {'TOTAL_ASSETS' in cols_lower}")
                print(f"  含 REPORT_DATE: {'REPORT_DATE' in bs.columns}")
                print(f"  含 report_date: {'report_date' in bs.columns}")
    except Exception as e:
        print(f"  失败: {type(e).__name__}: {str(e)[:150]}")

    # 3. 东财现金流表
    print("\n--- 3. 东财现金流量表 stock_cash_flow_sheet_by_report_em ---")
    try:
        cf = ak.stock_cash_flow_sheet_by_report_em(symbol=code)
        if cf is None or cf.empty:
            print("  空")
        else:
            print(f"  行数: {len(cf)}")
            print(f"  列名(前15): {list(cf.columns)[:15]}")
    except Exception as e:
        print(f"  失败: {type(e).__name__}: {str(e)[:150]}")

    # 4. 模拟 sync_code 的 fetch_quarterly + merge
    print("\n--- 4. 模拟 sync 链路 ---")
    try:
        from scripts.sync_akshare_financials import fetch_quarterly

        data = fetch_quarterly(code)
        print(f"  fetch_quarterly 返回 {len(data)} 个报告期")
        for period in sorted(data.keys())[-3:]:
            keys = list(data[period].keys())
            print(f"    {period}: {len(keys)} 字段 {keys[:8]}")
            has_bal = any(k in ("总资产", "总负债", "股东权益合计") for k in keys)
            has_cf = any("现金流" in k for k in keys)
            print(f"      balance字段={'有' if has_bal else '无'} cashflow字段={'有' if has_cf else '无'}")
    except Exception as e:
        print(f"  失败: {type(e).__name__}: {str(e)[:200]}")


if __name__ == "__main__":
    main()
