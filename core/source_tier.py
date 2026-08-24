# -*- coding: utf-8 -*-
"""来源可信度分层 — evidence_pool 的地基。

P3-A 落地：EvidenceLevel 七级枚举此前采集端未填。本模块按来源文本/
域名给出 (tier, weight)，供研究阶段过滤与引用附录标注。

层级（weight 用于后续加权聚合）：
  official 1.0 : 监管/交易所/公司法定披露
  broker   0.8 : 持牌券商研究所
  media    0.6 : 主流财经媒体/数据终端
  social   0.3 : 社区/自媒体
  unknown  0.5 : 无法识别（保守中位）
"""

from __future__ import annotations

import re

_TIERS = {
    "official": (
        1.0,
        (
            "巨潮",
            "cninfo",
            "上交所",
            "深交所",
            "sse",
            "szse",
            "sec.gov",
            "公司公告",
            "公司年报",
            "公司季报",
            "三季报",
            "年报",
            "招股书",
            "港交所",
            "hkex",
            "证监会",
        ),
    ),
    "broker": (
        0.8,
        (
            "中金",
            "高盛",
            " Goldman".lower(),
            "morgan",
            "摩根",
            "中信证券",
            "中信建投",
            "国泰君安",
            "华泰",
            "海通",
            "招商证券",
            "广发",
            "天风",
            "国信",
            "兴业证券",
            "东吴",
            "民生证券",
            "开源证券",
            "研报",
        ),
    ),
    "media": (
        0.6,
        (
            "财联社",
            "新浪财经",
            "东方财富",
            "eastmoney",
            "证券时报",
            "上海证券报",
            "中国证券报",
            "21世纪",
            "华尔街见闻",
            "彭博",
            "bloomberg",
            "路透",
            "reuters",
            "wind",
        ),
    ),
    "social": (
        0.3,
        ("雪球", "微博", "知乎", "微信公众号", "twitter", "x.com", "reddit"),
    ),
}


def score_source(source: str) -> tuple[str, float]:
    """返回 (tier, weight)。识别顺序 official→broker→media→social。"""
    s = (source or "").lower()
    if not s:
        return "unknown", 0.5
    for tier in ("official", "broker", "media", "social"):
        w, kws = _TIERS[tier]
        for kw in kws:
            if kw.lower() in s:
                return tier, w
    # 域名启发
    if re.search(r"https?://(www\.)?(sse|szse|cninfo|hkex)\.", s):
        return "official", 1.0
    return "unknown", 0.5


def evidence_pool_stats(collected_data: dict) -> dict:
    """统计采集数据的来源分层分布 {tier: count}（enrich items 优先）。"""
    cd = collected_data or {}
    tiers: dict[str, int] = {}
    items = cd.get("items") if isinstance(cd.get("items"), list) else []
    for it in items or []:
        if isinstance(it, dict):
            tier, _ = score_source(str(it.get("source", "")))
            tiers[tier] = tiers.get(tier, 0) + 1
    if not tiers:
        for k, v in (cd.get("sources") or {}).items():
            tier, _ = score_source(str(k))
            tiers[tier] = tiers.get(tier, 0) + 1
    return tiers


def high_confidence_ratio(collected_data: dict) -> float:
    """高置信（official+broker）占比；无来源时返回 0。"""
    tiers = evidence_pool_stats(collected_data)
    total = sum(tiers.values())
    if not total:
        return 0.0
    hi = tiers.get("official", 0) + tiers.get("broker", 0)
    return round(hi / total, 3)
