#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 Round 4 G/H 全球数据空壳（2026-08-01）

问题：
  global_leaders.json 34家全 yfinance FAIL: Too Many Requests（Yahoo 限流）
  us_stocks.db 0 行（同上）
  Marvis 脚本只记录 FAIL 未用 Tavily 回填 → 空壳数据污染分析

修复：
  1. yfinance 加指数退避重试（0.5→1→2→4s），降低限流
  2. yfinance 失败 → Tavily 搜真实财报数字回填（带 URL）
  3. 幂等：已有数据的 ticker 跳过
  4. 失败隔离：单只失败不中断

用法（主机跑）:
    python scripts/fix_global_data.py              # 修 G+H
    python scripts/fix_global_data.py --skip-h     # 只修 G
    python scripts/fix_global_data.py --tickers AAPL,MSFT  # 只修指定
"""

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# ── 美股 30（任务 H）──
TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "AMZN",
    "META",
    "TSLA",
    "AVGO",
    "ORCL",
    "AMD",
    "INTC",
    "QCOM",
    "ASML",
    "AMAT",
    "LRCX",
    "JPM",
    "BAC",
    "WMT",
    "KO",
    "PEP",
    "JNJ",
    "PFE",
    "LLY",
    "MRK",
    "XOM",
    "CVX",
    "CAT",
    "BA",
    "DIS",
    "NFLX",
]

# ── 全球龙头（任务 G）：(行业, 公司, ticker, 描述) ──
LEADERS = [
    ("半导体设备", "ASML", "ASML", "EUV光刻机"),
    ("半导体设备", "应用材料", "AMAT", "薄膜沉积/刻蚀设备"),
    ("半导体设计", "英伟达", "NVDA", "GPU/AI芯片"),
    ("半导体设计", "高通", "QCOM", "手机SoC"),
    ("半导体设计", "博通", "AVGO", "定制芯片/网络"),
    ("消费电子", "苹果", "AAPL", "智能手机"),
    ("消费电子", "三星电子", "005930.KS", "存储/手机"),
    ("汽车", "特斯拉", "TSLA", "电动车"),
    ("汽车", "丰田", "7203.T", "汽车"),
    ("新能源", "宁德时代", "300750.SZ", "动力电池"),
    ("云计算/软件", "微软", "MSFT", "云计算/AI"),
    ("云计算/软件", "甲骨文", "ORCL", "数据库/云"),
    ("互联网", "谷歌", "GOOGL", "搜索/广告"),
    ("互联网", "亚马逊", "AMZN", "电商/云"),
    ("互联网", "Meta", "META", "社交/广告"),
    ("医药", "辉瑞", "PFE", "创新药"),
    ("医药", "礼来", "LLY", "代谢/GIP药物"),
    ("医药", "强生", "JNJ", "医药/器械"),
    ("医疗器械", "美敦力", "MDT", "心血管器械"),
    ("医疗器械", "雅培", "ABT", "诊断/器械"),
    ("化工", "巴斯夫", "BAS.DE", "综合化工"),
    ("化工", "陶氏", "DOW", "材料化工"),
    ("工业", "西门子", "SIE.DE", "工业自动化"),
    ("工业", "ABB", "ABBN.SW", "电气自动化"),
    ("油气", "埃克森美孚", "XOM", "油气"),
    ("油气", "雪佛龙", "CVX", "油气"),
    ("银行", "摩根大通", "JPM", "银行"),
    ("零售", "沃尔玛", "WMT", "零售"),
    ("食品饮料", "可口可乐", "KO", "饮料"),
    ("食品饮料", "百事", "PEP", "食品饮料"),
]


def _to_yi(v):
    """美元 → 亿美元"""
    if v is None:
        return None
    try:
        return round(float(v) / 1e8, 2)
    except (TypeError, ValueError):
        return None


def _yf_info(ticker: str) -> dict:
    """yfinance 拉 info，指数退避重试。失败返回 {}"""
    import yfinance as yf

    for attempt, delay in enumerate([0.5, 1.0, 2.0, 4.0]):
        try:
            info = yf.Ticker(ticker).info
            if info and info.get("totalRevenue"):
                return info
        except Exception as e:
            if attempt < 3:
                print(f"  [RETRY {attempt + 1}] {ticker}: {str(e)[:50]}")
                time.sleep(delay)
    return {}


def _tavily_financial(ticker: str, company: str) -> dict:
    """Tavily 搜真实财报数字回填。返回 {revenue, net_profit, market_cap, pe, source}"""
    try:
        from tavily import TavilyClient

        key = os.environ.get("TAVILY_API_KEY", "")
        if not key:
            return {}
        tc = TavilyClient(api_key=key)
        r = tc.search(query=f"{company} {ticker} 2025 revenue net income market cap", max_results=3)
        urls = [res.get("url", "") for res in r.get("results", []) if res.get("url")]
        source = urls[0] if urls else f"tavily: {company} {ticker}"
        # 从搜索结果粗略提取数字（真实来源 URL 保证可追溯）
        content = " ".join(res.get("content", "") for res in r.get("results", [])[:2])
        import re

        rev = None
        m = re.search(r"(\d+\.?\d*)\s*(?:trillion|billion|million|亿|万亿|十亿)", content)
        if m:
            num = float(m.group(1))
            unit = m.group(2)
            mult = {"trillion": 1e12, "billion": 1e9, "million": 1e6, "亿": 1e8, "万亿": 1e12, "十亿": 1e10}
            rev = num * mult.get(unit, 1e9)
        return {
            "revenue": _to_yi(rev),
            "net_profit": None,
            "market_cap": None,
            "pe": None,
            "source": source,
            "partial": rev is not None,
        }
    except Exception as e:
        print(f"  [TAVILY] {ticker}: {str(e)[:60]}")
        return {}


def fix_h(skip: set) -> None:
    """修 us_stocks.db（30 只美股）"""
    db_path = DATA / "us_stocks.db"
    con = sqlite3.connect(str(db_path))
    con.execute("""CREATE TABLE IF NOT EXISTS us_stocks (
      ticker TEXT, as_of TEXT, revenue REAL, net_profit REAL,
      market_cap REAL, pe_ttm REAL, pb REAL, source TEXT,
      PRIMARY KEY (ticker, as_of))""")
    tickers = [t for t in TICKERS if t not in skip]
    print(f"\n=== 任务 H: 修 us_stocks.db ({len(tickers)} 只) ===")
    filled = 0
    for t in tickers:
        # 已有数据跳过（幂等）
        existing = con.execute("SELECT COUNT(*) FROM us_stocks WHERE ticker=?", (t,)).fetchone()[0]
        if existing > 0:
            print(f"  [SKIP] {t} 已有数据")
            continue
        info = _yf_info(t)
        if info:
            row = (
                t,
                "2026-08-01",
                _to_yi(info.get("totalRevenue")),
                _to_yi(info.get("netIncomeToCommon")),
                _to_yi(info.get("marketCap")),
                round(info["trailingPE"], 2) if info.get("trailingPE") else None,
                round(info["priceToBook"], 2) if info.get("priceToBook") else None,
                "yfinance: Ticker.info",
            )
            con.execute("INSERT OR REPLACE INTO us_stocks VALUES (?,?,?,?,?,?,?,?)", row)
            con.commit()
            filled += 1
            print(f"  [H] {t}: rev={row[2]} 市值={row[4]} PE={row[5]}")
        else:
            # yfinance 失败 → Tavily 兜底
            tf = _tavily_financial(t, t)
            if tf.get("revenue"):
                row = (t, "2026-08-01", tf["revenue"], tf["net_profit"], tf["market_cap"], tf["pe"], None, tf["source"])
                con.execute("INSERT OR REPLACE INTO us_stocks VALUES (?,?,?,?,?,?,?,?)", row)
                con.commit()
                filled += 1
                print(f"  [H-TAVILY] {t}: rev={row[2]} (source={tf['source'][:40]})")
            else:
                print(f"  [H] {t} FAIL: yfinance限流+Tavily无数据")
        time.sleep(1.0)  # 限流保护
    con.close()
    print(f"H 完成: 新增 {filled} 只")


def fix_g(skip: set) -> None:
    """修 global_leaders.json"""
    path = DATA / "global_leaders.json"
    # 读现有（保留非 None 的）
    existing_leaders = {}
    if path.exists():
        try:
            d = json.load(open(path))
            for l in d.get("leaders", []):
                if l.get("revenue_2025"):
                    existing_leaders[l["ticker"]] = l
        except Exception:
            pass
    print(f"\n=== 任务 G: 修 global_leaders.json（{len(LEADERS)} 家，已有{len(existing_leaders)}家有数据）===")
    leaders = list(existing_leaders.values())
    for ind, comp, tk, desc in LEADERS:
        if tk in existing_leaders or tk in skip:
            continue
        info = _yf_info(tk)
        if info:
            leaders.append(
                {
                    "industry": ind,
                    "company": comp,
                    "ticker": tk,
                    "revenue_2025": _to_yi(info.get("totalRevenue")),
                    "net_profit_2025": _to_yi(info.get("netIncomeToCommon")),
                    "market_cap": _to_yi(info.get("marketCap")),
                    "pe_ttm": round(info["trailingPE"], 2) if info.get("trailingPE") else None,
                    "global_market_share": desc,
                    "source": "yfinance: Ticker.info",
                }
            )
            print(f"  [G] {comp}: rev={_to_yi(info.get('totalRevenue'))} 市值={_to_yi(info.get('marketCap'))}")
        else:
            tf = _tavily_financial(tk, comp)
            if tf.get("revenue"):
                leaders.append(
                    {
                        "industry": ind,
                        "company": comp,
                        "ticker": tk,
                        "revenue_2025": tf["revenue"],
                        "net_profit_2025": tf["net_profit"],
                        "market_cap": tf["market_cap"],
                        "pe_ttm": tf["pe"],
                        "global_market_share": desc,
                        "source": tf["source"],
                    }
                )
                print(f"  [G-TAVILY] {comp}: rev={tf['revenue']} ({tf['source'][:40]})")
            else:
                print(f"  [G] {comp} FAIL: yfinance限流+Tavily无数据")
        time.sleep(1.0)
    path.write_text(
        json.dumps({"leaders": leaders, "source": "yfinance + tavily"}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with_data = sum(1 for l in leaders if l.get("revenue_2025"))
    print(f"G 完成: 共{len(leaders)}家，{with_data}家有数据")


def main():
    parser = argparse.ArgumentParser(description="修复 Round4 G/H 全球数据空壳")
    parser.add_argument("--skip-g", action="store_true", help="跳过任务 G")
    parser.add_argument("--skip-h", action="store_true", help="跳过任务 H")
    parser.add_argument("--tickers", default="", help="只处理指定 ticker(逗号分隔)")
    args = parser.parse_args()

    skip = set(t.strip().upper() for t in args.tickers.split(",") if t.strip())
    if not args.skip_h:
        fix_h(skip)
    if not args.skip_g:
        fix_g(skip)
    print("\n完成。数据文件：")
    print(f"  {DATA / 'us_stocks.db'}")
    print(f"  {DATA / 'global_leaders.json'}")


if __name__ == "__main__":
    main()
