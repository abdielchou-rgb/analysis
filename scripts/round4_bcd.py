#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 4 任务 B/C/D 数据抓取（2026-08-01）

B: 政策库 data/policy_db.json（30行业 × ≥3条）
C: 产业链 data/industry_chain.json（重点行业上游/中游/下游 + 价格传导）
D: 渗透率 data/industry_penetration.json（30行业细分赛道）

数据源：Tavily 网页搜索（带 URL source，FP2 合规）
用法（主机跑，需 TAVILY_API_KEY）:
    python scripts/round4_bcd.py --task b
    python scripts/round4_bcd.py --task c
    python scripts/round4_bcd.py --task d
    python scripts/round4_bcd.py --task all
"""

import argparse
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 30 个重点行业
INDUSTRIES = [
    "半导体",
    "消费电子",
    "汽车",
    "新能源汽车",
    "光伏",
    "风电",
    "锂电",
    "储能",
    "白酒",
    "乳制品",
    "医药",
    "医疗器械",
    "CXO",
    "创新药",
    "军工",
    "工程机械",
    "重卡",
    "家电",
    "面板",
    "LED",
    "PCB",
    "钢铁",
    "煤炭",
    "化工",
    "有色",
    "黄金",
    "银行",
    "保险",
    "房地产",
    "建筑",
]


def _tavily_search(query: str, max_results: int = 4) -> list:
    """Tavily 搜索，返回 [{title, url, content}]"""
    try:
        from tavily import TavilyClient

        key = os.environ.get("TAVILY_API_KEY", "")
        if not key:
            print("[!] TAVILY_API_KEY 未设置")
            return []
        tc = TavilyClient(api_key=key)
        r = tc.search(query=query, max_results=max_results)
        return [
            {"title": res.get("title", ""), "url": res.get("url", ""), "content": res.get("content", "")}
            for res in r.get("results", [])
            if res.get("url")
        ]
    except Exception as e:
        print(f"[!] Tavily 失败: {str(e)[:80]}")
        return []


def _extract_bullets(query: str, industry: str, max_bullets: int = 4) -> list:
    """搜索并提取数据点条目（每条带 URL）"""
    results = _tavily_search(query)
    bullets = []
    for res in results:
        content = res["content"].strip()
        if not content or len(content) < 20:
            continue
        # 取第一句作为数据点（截断 150 字）
        sent = content.split("。")[0].split(".")[0][:150]
        if len(sent) < 15:
            continue
        bullets.append(f"• {sent} (来源: {res['url']})")
        if len(bullets) >= max_bullets:
            break
    return bullets


def task_b():
    """政策库 data/policy_db.json"""
    path = DATA / "policy_db.json"
    # 读现有
    existing = []
    if path.exists():
        try:
            existing = json.load(open(path)).get("policies", [])
        except Exception:
            existing = []
    print(f"=== 任务 B: 政策库（已有{len(existing)}条）===")
    seen = {(p.get("industry"), p.get("title")) for p in existing}
    added = 0
    for ind in INDUSTRIES:
        queries = [
            f"{ind} 政策 2025 2026 支持 规划 补贴",
            f"{ind} 十五五 政策 方向",
            f"{ind} 监管 法规 2026 限制",
        ]
        for q in queries:
            results = _tavily_search(q, max_results=3)
            for res in results:
                title = res.get("title", "")[:60]
                url = res.get("url", "")
                content = res.get("content", "")[:100]
                if not title or not url:
                    continue
                if (ind, title) in seen:
                    continue
                seen.add((ind, title))
                # 粗略方向判断
                direction = (
                    1
                    if any(k in content for k in ["支持", "鼓励", "补贴", "规划", "基金"])
                    else (-1 if any(k in content for k in ["限制", "监管", "禁止", "整治"]) else 0)
                )
                existing.append(
                    {
                        "industry": ind,
                        "title": title,
                        "date": "2025",
                        "level": "国家级",
                        "direction": direction,
                        "summary": content,
                        "related_sectors": [],
                        "source": url,
                    }
                )
                added += 1
            time.sleep(0.5)  # 限流保护
    path.write_text(
        json.dumps({"policies": existing, "source": "tavily"}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"B 完成: 共{len(existing)}条（新增{added}），写入 {path}")


def task_c():
    """产业链 data/industry_chain.json"""
    path = DATA / "industry_chain.json"
    existing = []
    if path.exists():
        try:
            existing = json.load(open(path)).get("chains", [])
        except Exception:
            existing = []
    print(f"=== 任务 C: 产业链（已有{len(existing)}条）===")
    # 重点行业先建，普通行业看 Tavily
    focus = ["半导体", "新能源汽车", "光伏", "锂电", "医药", "白酒", "钢铁", "煤炭", "化工", "消费电子"]
    seen = {c.get("industry") for c in existing}
    for ind in focus:
        if ind in seen:
            continue
        results = _tavily_search(f"{ind} 产业链 上游 中游 下游 成本结构", max_results=3)
        chain = {
            "industry": ind,
            "upstream": [],
            "midstream": [],
            "downstream": [],
            "price_links": [],
            "margin_flow": "",
            "source": "",
        }
        for res in results:
            if res.get("url") and not chain["source"]:
                chain["source"] = res["url"]
            content = res.get("content", "")
            # 提取上下游关键词
            if "上游" in content:
                chain["upstream"] = [s.strip() for s in content.split("上游")[1][:60].split("、")[:4] if s.strip()]
            if "中游" in content:
                chain["midstream"] = [s.strip() for s in content.split("中游")[1][:60].split("、")[:4] if s.strip()]
            if "下游" in content:
                chain["downstream"] = [s.strip() for s in content.split("下游")[1][:60].split("、")[:4] if s.strip()]
        if chain["source"]:
            existing.append(chain)
            seen.add(ind)
            print(f"  [C] {ind}: 上下游 {len(chain['upstream'])}/{len(chain['downstream'])}")
        time.sleep(0.5)
    path.write_text(
        json.dumps({"chains": existing, "source": "tavily"}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"C 完成: 共{len(existing)}条，写入 {path}")


def task_d():
    """渗透率 data/industry_penetration.json"""
    path = DATA / "industry_penetration.json"
    existing = []
    if path.exists():
        try:
            existing = json.load(open(path)).get("penetration", [])
        except Exception:
            existing = []
    print(f"=== 任务 D: 渗透率（已有{len(existing)}条）===")
    segments = {
        "新能源汽车": "电动乘用车",
        "光伏": "光伏发电",
        "锂电": "动力电池",
        "储能": "电化学储能",
        "消费电子": "智能手机",
        "汽车": "L2级辅助驾驶",
        "家电": "智能家居",
        "医药": "创新药",
        "半导体": "先进制程芯片",
    }
    seen = {(p.get("industry"), p.get("segment")) for p in existing}
    for ind, seg in segments.items():
        if (ind, seg) in seen:
            continue
        results = _tavily_search(f"{seg} 渗透率 2025 中国", max_results=3)
        for res in results:
            content = res.get("content", "")
            import re

            m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", content)
            if m:
                pct = float(m.group(1))
                life = (
                    "导入期"
                    if pct < 5
                    else "成长期早期"
                    if pct < 30
                    else "成长期"
                    if pct < 60
                    else "成熟期"
                    if pct < 85
                    else "衰退期"
                )
                existing.append(
                    {
                        "industry": ind,
                        "segment": seg,
                        "penetration_pct": pct,
                        "as_of": "2025",
                        "life_cycle": life,
                        "growth_curve": "S曲线",
                        "source": res.get("url", "tavily"),
                    }
                )
                seen.add((ind, seg))
                print(f"  [D] {seg}: {pct}% → {life}")
                break
        time.sleep(0.5)
    path.write_text(
        json.dumps({"penetration": existing, "source": "tavily"}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"D 完成: 共{len(existing)}条，写入 {path}")


def main():
    parser = argparse.ArgumentParser(description="Round4 B/C/D 数据抓取")
    parser.add_argument("--task", choices=["b", "c", "d", "all"], default="all")
    args = parser.parse_args()
    if args.task in ("b", "all"):
        task_b()
    if args.task in ("c", "all"):
        task_c()
    if args.task in ("d", "all"):
        task_d()
    print("\n全部完成")


if __name__ == "__main__":
    main()
