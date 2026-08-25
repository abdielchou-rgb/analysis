#!/usr/bin/env python3
"""P0-② 分业务线收入拆分库 — 消除"盈利预测无拆解"

为沪深300/中证1000 每只标的补主营构成（分业务收入/占比/增速），
供报告盈利预测章节做分业务线拆解。

用法:
    python scripts/build_segment_revenue.py --index 000300 --workers 2
    python scripts/build_segment_revenue.py --ticker 603662

数据来源: akshare (stock_zygc_em 主营构成)
输出: data/segment_revenue.json
  覆盖 ~300 只（沪深300 优先）

FP2 零编造: 数据来自 akshare，无分业务数据标空
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT = ROOT / "data" / "segment_revenue.json"


def _num(v):
    try:
        f = float(v)
        return f if f == f else None  # NaN → None
    except (TypeError, ValueError):
        return None


def build_for_ticker(code: str) -> dict | None:
    """为单只标的提取主营构成（分业务收入/占比）— 东财 emweb 直连。"""
    import requests

    try:
        prefix = "SH" if code.startswith(("6", "9")) else "SZ"
        url = "https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://emweb.securities.eastmoney.com/",
        }
        r = requests.get(url, params={"code": f"{prefix}{code}"}, headers=headers, timeout=15)
        d = r.json()
        zg = d.get("zygcfx") or []
        if not zg:
            return None
        # 取最新报告期，且优先"按行业"(MAINOP_TYPE=1)
        dates = sorted({str(x.get("REPORT_DATE", "")) for x in zg}, reverse=True)
        latest = dates[0] if dates else ""
        zg = [x for x in zg if str(x.get("REPORT_DATE", "")) == latest]
        best_type = None
        for t in ("1", "2", "3"):
            rows = [x for x in zg if str(x.get("MAINOP_TYPE", "")) == t]
            if rows:
                best_type = rows
                break
        rows = best_type or zg
        segments = []
        for row in rows:
            item = str(row.get("ITEM_NAME", "")).strip()
            if not item or item in ("nan", "None", ""):
                continue
            rev = _num(row.get("MAIN_BUSINESS_INCOME"))
            ratio = _num(row.get("MBI_RATIO"))
            if rev or ratio:
                segments.append(
                    {
                        "name": item[:20],
                        "revenue": rev,
                        "pct": round(ratio * 100, 2) if ratio else None,
                        "growth": None,
                    }
                )
        if not segments:
            return None
        segments = sorted(segments, key=lambda s: -(s["pct"] or 0))[:8]
        period = str(rows[0].get("REPORT_DATE", "")).split(" ")[0]
        return {
            "segments": segments,
            "period": period or datetime.now().strftime("%Y-%m-%d"),
            "source": "eastmoney emweb 直连",
        }
    except Exception as e:
        print(f"[{code}] 主营构成失败: {str(e)[:100]}")
        return None


def build_index(index: str, workers: int) -> dict:
    """为指数成分全量构建分业务收入库。"""
    try:
        import akshare as ak

        df = ak.index_stock_cons_csindex(symbol=index)
        if df is None or df.empty:
            print(f"[{index}] 成分获取失败")
            return {}
        codes = [str(c).zfill(6) for c in df["成分券代码"].tolist()]
        print(f"[{index}] {len(codes)} 只成分股")
    except Exception as e:
        print(f"[{index}] 失败: {e}")
        return {}

    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(build_for_ticker, c): c for c in codes}
        for fut in as_completed(futures):
            code = futures[fut]
            try:
                r = fut.result()
                if r:
                    results[code] = r
            except Exception:
                continue
    return results


def main():
    parser = argparse.ArgumentParser(description="分业务线收入拆分库构建")
    parser.add_argument("--index", default="000300", help="指数成分（逗号分隔）")
    parser.add_argument("--ticker", default=None, help="仅构建单只标的")
    parser.add_argument("--workers", "-w", type=int, default=2, help="并发数")
    args = parser.parse_args()

    try:
        import akshare as ak  # noqa: F401
    except ImportError:
        print("[错误] 需在用户机运行（akshare 不可用）")
        sys.exit(1)

    if args.ticker:
        code = args.ticker.zfill(6)
        r = build_for_ticker(code)
        result = {code: r} if r else {}
    else:
        result = {}
        for idx in [i.strip() for i in args.index.split(",")]:
            result.update(build_index(idx, args.workers))
            time.sleep(1)

    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[完成] 分业务收入库: {len(result)} 只 → {OUTPUT}")

    if result:
        sample = list(result.keys())[0]
        print(f"[验证] {sample}: {json.dumps(result[sample], ensure_ascii=False)[:200]}")


if __name__ == "__main__":
    main()
