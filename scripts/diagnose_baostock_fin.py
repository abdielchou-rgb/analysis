#!/usr/bin/env python3
"""诊断 Baostock 财务接口 — 确认正确的调用方式

用法: python scripts/diagnose_baostock_fin.py "600519"
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "600519"
    import baostock as bs

    lg = bs.login()
    print(f"login: {lg.error_code} {lg.error_msg}")

    # 确定代码格式
    bs_code = f"sh.{code}" if code.startswith("6") else f"sz.{code}"
    print(f"代码: {bs_code}")

    # 1. 测试 query_profit_data 不同 year 参数
    print("\n=== query_profit_data ===")
    for year in ["", "2024", "2025"]:
        rs = bs.query_profit_data(code=bs_code, year=year, quarter="")
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
        print(f"  year={year!r}: {len(rows)} 行")
        if rows:
            print(f"    首行: {rows[0]}")
            print(f"    字段: {rs.fields}")
            break  # 找到能返回的年份即可

    # 2. 测试 query_balance_data
    print("\n=== query_balance_data ===")
    for year in ["", "2024", "2025"]:
        rs = bs.query_balance_data(code=bs_code, year=year, quarter="")
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
        print(f"  year={year!r}: {len(rows)} 行")
        if rows:
            print(f"    首行: {rows[0]}")
            break

    # 3. 测试 query_cash_flow_data
    print("\n=== query_cash_flow_data ===")
    for year in ["", "2024", "2025"]:
        rs = bs.query_cash_flow_data(code=bs_code, year=year, quarter="")
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
        print(f"  year={year!r}: {len(rows)} 行")
        if rows:
            print(f"    首行: {rows[0]}")
            break

    bs.logout()
    print("\n[完成]")


if __name__ == "__main__":
    main()
