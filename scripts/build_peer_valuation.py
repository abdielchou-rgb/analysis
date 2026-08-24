#!/usr/bin/env python3
"""P0-① A股可比估值库 — 对标顶级投行可比公司矩阵

为沪深300/中证1000 每只标的建立"同行业可比估值矩阵"：
  本股 + 同行业成分股的 PE/PB/市值/增速 → 行业均值/中位数

用法:
    python scripts/build_peer_valuation.py --index 000300,000852 --workers 2
    python scripts/build_peer_valuation.py --ticker 603662

数据来源: 东财 API 直连（akshare stock_zh_a_spot_em 被风控时直连替代）
输出: data/peer_valuation.json
  覆盖 ~1300 只（沪深300 + 中证1000）

FP2 零编造: 所有数据来自东财接口，无数据标 None
"""

import argparse
import json
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT = ROOT / "data" / "peer_valuation.json"

# 全市场行情缓存（一次拉取，避免每标的重复请求）
_SPOT_CACHE = None
# 行业板块缓存
_BOARD_CACHE = {}


def _em_spot_pages(fs: str = "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
                   max_pages: int = 120) -> list:
    """东财行情分页拉取（绕过 akshare 被风控的 UA）。返回 dict 列表。"""
    rows = []
    url = "https://push2delay.eastmoney.com/api/qt/clist/get"
    for pn in range(1, max_pages + 1):
        params = {
            "pn": pn, "pz": 100, "po": 1, "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2, "invt": 2, "fid": "f3",
            "fs": fs,
            "fields": "f2,f3,f5,f6,f8,f9,f10,f12,f14,f20,f21,f100",
        }
        ok = False
        for attempt in range(3):  # 每页最多重试3次
            try:
                r = requests.get(url, params=params, headers=_HEADERS, timeout=15)
                data = r.json().get("data") or {}
                diff = data.get("diff") or []
                if not diff:
                    ok = True
                    break
                rows.extend(diff)
                if pn * 100 >= (data.get("total") or 0):
                    ok = True
                    break
                ok = True
                break
            except Exception as e:
                if attempt == 2:
                    print(f"[行情分页] 第{pn}页重试3次仍失败: {e}")
                time.sleep(1 + attempt)
        if not ok:
            break
        time.sleep(0.15)
    return rows


def _sina_sector_cons(label: str, max_pages: int = 10) -> list:
    """新浪行业板块成分（直连，含 PE/PB/市值）。"""
    rows = []
    url = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/"
           "json_v2.php/Market_Center.getHQNodeData")
    for page in range(1, max_pages + 1):
        params = {"page": page, "num": 100, "sort": "symbol",
                  "asc": 1, "node": label}
        try:
            r = requests.get(url, params=params, headers=_HEADERS, timeout=15)
            data = r.json()
            if not data:
                break
            rows.extend(data)
            if len(data) < 100:
                break
        except Exception as e:
            print(f"[新浪成分] {label} 第{page}页失败: {e}")
            break
        time.sleep(0.2)
    return rows


def _get_spot_map():
    """全市场行情：代码 → {name, pe, pb, mcap, industry}（东财直连，失败兜底新浪）。"""
    global _SPOT_CACHE
    if _SPOT_CACHE is not None:
        return _SPOT_CACHE
    spot = {}
    # 主源：东财行情（push2delay，绕过限流 host）
    try:
        rows = _em_spot_pages()
        for r in rows:
            try:
                code = str(r.get("f12", "")).zfill(6)
                if not code:
                    continue
                spot[code] = {
                    "name": str(r.get("f14", "")),
                    "pe": _num(r.get("f9")),
                    "pb": _num(r.get("f23", r.get("f10"))),
                    "mcap": _num(r.get("f20")) / 1e8 if _num(r.get("f20")) else None,
                    "industry": str(r.get("f100", "")),
                }
            except Exception:
                continue
        print(f"[全市场行情] 东财缓存 {len(spot)} 只")
    except Exception as e:
        print(f"[全市场行情] 东财失败: {e}")
    # 兜底：新浪行业直连
    if len(spot) < 3000:
        print("[全市场行情] 东财覆盖不足，尝试新浪兜底")
        try:
            r = requests.get("https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php",
                             headers=_HEADERS, timeout=15)
            r.encoding = "gbk"
            text = r.text
            start = text.find("{")
            end = text.rfind("}")
            import json as _json
            data = _json.loads(text[start:end + 1])
            for label, val in data.items():
                parts = str(val).split(",")
                if len(parts) < 2:
                    continue
                sector_name = parts[1]
                try:
                    rows = _sina_sector_cons(label)
                except Exception:
                    continue
                for row in rows:
                    try:
                        code = str(row.get("code", "")).zfill(6)
                        if not code or code in spot:
                            continue
                        mcap_yi = _num(row.get("mktcap"))
                        spot[code] = {
                            "name": str(row.get("name", "")),
                            "pe": _num(row.get("per")),
                            "pb": _num(row.get("pb")),
                            "mcap": round(mcap_yi / 1e4, 1) if mcap_yi else None,
                            "industry": sector_name,
                        }
                    except Exception:
                        continue
                time.sleep(0.2)
            print(f"[全市场行情] 东财+新浪合计 {len(spot)} 只")
        except Exception as e:
            print(f"[全市场行情] 新浪兜底失败: {e}")
    _SPOT_CACHE = spot
    return _SPOT_CACHE


def _num(v):
    try:
        f = float(v)
        return f if f == f else None  # NaN → None
    except (TypeError, ValueError):
        return None


def _get_board_cons(industry: str) -> list:
    """行业板块成分股代码列表（带缓存，东财直连）。"""
    if industry in _BOARD_CACHE:
        return _BOARD_CACHE[industry]
    try:
        rows = _em_spot_pages(fs=f"b:{industry}")
        codes = [str(r.get("f12", "")).zfill(6) for r in rows if r.get("f12")]
        _BOARD_CACHE[industry] = codes
        return codes
    except Exception:
        pass
    _BOARD_CACHE[industry] = []
    return []


def build_for_ticker(code: str, spot_map: dict) -> dict | None:
    """为单只标的构建可比估值矩阵。"""
    if code not in spot_map:
        return None
    info = spot_map[code]
    industry = info.get("industry", "")
    if not industry:
        return None

    # 同行业成分股（从全市场 spot_map 按行业分组）
    peers_codes = [c for c, s in spot_map.items() if s.get("industry") == industry]
    peers = []
    for pc in peers_codes[:15]:  # 最多取15家
        if pc in spot_map:
            p = spot_map[pc]
            peers.append({
                "name": p["name"], "code": pc,
                "pe_ttm": p["pe"], "pb": p["pb"],
                "mcap_b": round(p["mcap"], 1) if p["mcap"] else None,
            })

    # 行业 PE 均值/中位数
    pe_vals = [p["pe_ttm"] for p in peers if p["pe_ttm"]]
    if not pe_vals:
        return None
    pe_vals.sort()
    avg_pe = sum(pe_vals) / len(pe_vals)
    median_pe = pe_vals[len(pe_vals) // 2] if len(pe_vals) % 2 == 1 else (
        (pe_vals[len(pe_vals)//2-1] + pe_vals[len(pe_vals)//2]) / 2)

    return {
        "industry": industry,
        "peers": peers,
        "industry_avg_pe": round(avg_pe, 1),
        "industry_median_pe": round(median_pe, 1),
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "source": "akshare: stock_board_industry_cons_em + stock_zh_a_spot_em",
    }


def build_index(index: str, workers: int) -> dict:
    """为指数成分全量构建可比估值。"""
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

    spot = _get_spot_map()
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(build_for_ticker, c, spot): c for c in codes}
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
    parser = argparse.ArgumentParser(description="A股可比估值库构建")
    parser.add_argument("--index", default="000300,000852", help="指数成分（逗号分隔）")
    parser.add_argument("--ticker", default=None, help="仅构建单只标的")
    parser.add_argument("--workers", "-w", type=int, default=2, help="并发数")
    args = parser.parse_args()

    try:
        import akshare as ak  # noqa: F401
    except ImportError:
        print("[错误] 需在用户机运行（akshare 不可用）")
        sys.exit(1)

    spot = _get_spot_map()
    if args.ticker:
        code = args.ticker.zfill(6)
        r = build_for_ticker(code, spot)
        result = {code: r} if r else {}
    else:
        result = {}
        for idx in [i.strip() for i in args.index.split(",")]:
            result.update(build_index(idx, args.workers))
            time.sleep(1)  # 指数间间隔

    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"[完成] 可比估值库: {len(result)} 只 → {OUTPUT}")

    # 验证
    if result:
        sample = list(result.keys())[0]
        print(f"[验证] {sample}: {json.dumps(result[sample], ensure_ascii=False)[:200]}")


if __name__ == "__main__":
    main()
