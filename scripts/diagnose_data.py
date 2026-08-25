#!/usr/bin/env python3
"""2hao-analyst 数据采集诊断 — 快速定位 AkShare 接口问题

用法:
    python scripts/diagnose_data.py "中芯国际"

只测试数据采集部分（不跑全管线），30 秒定位接口异常。
"""

import sys
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_block(name, fn):
    print(f"\n=== {name} ===")
    try:
        result = fn()
        if result:
            print(f"  [OK] 返回 {len(result) if hasattr(result, '__len__') else result} 项")
            return result
        else:
            print("  [--] 返回空（接口可用但无数据，或接口不可用）")
            return None
    except Exception as e:
        print(f"  [!!] 异常: {type(e).__name__}: {e}")
        traceback.print_exc(limit=3)
        return None


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else "中芯国际"
    print(f"诊断标的: {asset}")
    print(f"Python: {sys.version}")
    try:
        import akshare as ak

        print(f"AkShare 版本: {ak.__version__}")
    except ImportError as e:
        print(f"[!!] akshare 未安装: {e}")
        return 1

    # 提取股票代码
    import re

    code_match = re.search(r"(\d{6})", asset)
    code = code_match.group(1) if code_match else ""
    if not code:
        # 尝试用名字解析
        try:
            df = ak.stock_info_a_code_name()
            m = df[df["name"].str.contains(asset[:4], na=False)]
            if not m.empty:
                code = str(m.iloc[0]["code"]).zfill(6)
                print(f"  解析代码: {asset} -> {code}")
        except Exception as e:
            print(f"[!!] 代码解析失败: {e}")
    if not code:
        print("[!!] 无法确定股票代码")
        return 1

    # 1. 年度财务（已知可用）
    test_block(
        "1. 年度财务 stock_financial_abstract_ths",
        lambda: ak.stock_financial_abstract_ths(symbol=code, indicator="按年度"),
    )

    # 2. 主营构成（新）
    test_block("2. 主营构成 stock_zygc_em", lambda: ak.stock_zygc_em(symbol=code))

    # 3. 资金流（新）
    market = "sh" if code.startswith("6") else "sz"
    test_block(
        f"3. 个股资金流 stock_individual_fund_flow({market})",
        lambda: ak.stock_individual_fund_flow(stock=code, market=market),
    )

    # 4. 行业板块列表（新，同业第一步）
    test_block("4. 行业板块列表 stock_board_industry_name_em", lambda: ak.stock_board_industry_name_em())

    # 5. 找所属行业
    def locate_industry():
        df_board = ak.stock_board_industry_name_em()
        if df_board is None or df_board.empty:
            return None
        for _, row in df_board.iterrows():
            bname = str(row.get("板块名称", ""))
            try:
                df_cons = ak.stock_board_industry_cons_em(symbol=bname)
                if df_cons is not None and not df_cons.empty:
                    codes = df_cons["代码"].astype(str).str.zfill(6)
                    if code in codes.tolist():
                        return {"行业板块": bname}
            except Exception:
                continue
        return None

    test_block("5. 定位所属行业", locate_industry)

    # 6. 全市场行情（同业数据源）
    test_block("6. 全市场行情 stock_zh_a_spot_em", lambda: ak.stock_zh_a_spot_em())

    print("\n[完成] 请把上面输出贴给 Claude。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
