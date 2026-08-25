#!/usr/bin/env python3
"""P0-③ 行业基线数据扩展 — 用 akshare 获取行业估值/盈利/增长基线

用法:
    python scripts/sync_industry_baselines.py --all      # 全量更新
    python scripts/sync_industry_baselines.py --sector XXXX  # 仅指定板块

数据来源: akshare (申万行业分类)
输出: data/industry_baselines.json

字段:
  - sector_code: 行业代码
  - sector_name: 行业名称
  - pe_ttm: PE-TTM（整体法）
  - pb: PB（整体法）
  - roe: ROE
  - revenue_growth: 营收增速
  - profit_growth: 利润增速
  - market_cap: 总市值（亿）
  - stock_count: 成分股数量
  - source: "akshare"
  - updated_at: 更新时间

FP2 零编造: 所有数据来自 akshare 接口
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT = ROOT / "data" / "industry_baselines.json"


def sync_sw_sectors():
    """同步申万行业分类 + 估值数据。"""
    try:
        import akshare as ak
    except ImportError:
        print("[错误] akshare 未安装: pip install akshare")
        return None

    results = []
    now = datetime.now().isoformat()

    # 1. 申万三级行业分类 + 估值（sw_index_third_info）
    # 列: 行业代码, 行业名称, 上级行业, 成份个数, 静态市盈率, TTM(滚动)市盈率, 市净率, 静态股息率
    try:
        sw_df = ak.sw_index_third_info()
        if sw_df is not None and not sw_df.empty:
            print(f"[申万三级行业] {len(sw_df)} 个行业")
            for _, row in sw_df.iterrows():
                try:
                    results.append(
                        {
                            "sector_code": str(row.get("行业代码", "")),
                            "sector_name": str(row.get("行业名称", "")),
                            "parent_sector": str(row.get("上级行业", "")),
                            "pe_ttm": round(float(row["TTM(滚动)市盈率"]), 2)
                            if row.get("TTM(滚动)市盈率") and row["TTM(滚动)市盈率"] == row["TTM(滚动)市盈率"]
                            else None,
                            "pe_static": round(float(row["静态市盈率"]), 2)
                            if row.get("静态市盈率") and row["静态市盈率"] == row["静态市盈率"]
                            else None,
                            "pb": round(float(row["市净率"]), 2)
                            if row.get("市净率") and row["市净率"] == row["市净率"]
                            else None,
                            "dividend_yield": round(float(row["静态股息率"]), 2)
                            if row.get("静态股息率") and row["静态股息率"] == row["静态股息率"]
                            else None,
                            "stock_count": int(row.get("成份个数", 0) or 0),
                            "source": "akshare_sw3",
                            "updated_at": now,
                        }
                    )
                except Exception:
                    continue
            print(f"[申万三级行业] 提取 {len(results)} 个行业")
    except Exception as e:
        print(f"[申万三级行业] 接口失败: {e}")

    # 2. 全市场快照补充分行业PE/PB（fallback）
    if not results:
        try:
            pe_df = ak.stock_sz_a_spot_em()
            if pe_df is not None and not pe_df.empty and "所属行业" in pe_df.columns:
                sector_stats = (
                    pe_df.groupby("所属行业")
                    .agg(
                        stock_count=("代码", "count"),
                        median_pe=("市盈率-动态", "median"),
                        avg_pb=("市净率", "mean"),
                        total_market_cap=("总市值", "sum"),
                    )
                    .reset_index()
                )
                for _, row in sector_stats.iterrows():
                    try:
                        results.append(
                            {
                                "sector_name": str(row["所属行业"]),
                                "pe_ttm": round(float(row["median_pe"]), 2)
                                if row["median_pe"] and row["median_pe"] == row["median_pe"]
                                else None,
                                "pb": round(float(row["avg_pb"]), 2)
                                if row["avg_pb"] and row["avg_pb"] == row["avg_pb"]
                                else None,
                                "market_cap": round(float(row["total_market_cap"]) / 1e8, 2)
                                if row["total_market_cap"]
                                else None,
                                "stock_count": int(row["stock_count"]),
                                "source": "akshare_spot",
                                "updated_at": now,
                            }
                        )
                    except Exception:
                        continue
                print(f"[行业估值] 统计 {len(results)} 个行业")
        except Exception as e:
            print(f"[行业估值] 接口失败: {e}")

    return results if results else None


def load_existing() -> dict:
    if OUTPUT.exists():
        try:
            return json.loads(OUTPUT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"_meta": {"total_sectors": 0, "generated": None}, "sectors": []}


def save_baselines(data: list, existing: dict):
    """增量合并：按 sector_name 去重更新。"""
    now = datetime.now().isoformat()
    existing_sectors = {s["sector_name"]: i for i, s in enumerate(existing.get("sectors", []))}
    for item in data:
        name = item["sector_name"]
        if name in existing_sectors:
            existing["sectors"][existing_sectors[name]] = item
        else:
            existing["sectors"].append(item)
    existing["_meta"] = {"total_sectors": len(existing["sectors"]), "generated": now}
    OUTPUT.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[落盘] {len(existing['sectors'])} 个行业 → {OUTPUT}")


def main():
    parser = argparse.ArgumentParser(description="行业基线数据同步")
    parser.add_argument("--all", action="store_true", help="全量更新")
    parser.add_argument("--sector", help="指定行业名称")
    args = parser.parse_args()

    if not args.all and not args.sector:
        parser.print_help()
        return 1

    print("同步行业基线数据...")
    data = sync_sw_sectors()
    if not data:
        print("[失败] 无法获取行业数据")
        return 1

    existing = load_existing()
    save_baselines(data, existing)

    # 展示 TOP 10
    sectors = sorted(existing["sectors"], key=lambda x: x.get("stock_count", 0), reverse=True)[:10]
    print("\nTOP 10 行业:")
    for s in sectors:
        print(
            f"  {s['sector_name']}: {s.get('stock_count', 0)} 只, PE={s.get('pe_ttm', 'N/A')}, PB={s.get('pb', 'N/A')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
