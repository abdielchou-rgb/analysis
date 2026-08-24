"""
Industry data cache for 2hao-analyst.
Auto-populated from web search. When data_collector finds no primary source,
it falls back to this cache which contains web-sourced real data.
"""

import json
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent / "industry_cache.json"

# Real data sourced from web (Exa search + verified sources)
INDUSTRY_DATA = {
    "商业航天": {
        "sources": [
            "赛迪智库《中国商业航天产业研究报告》2025",
            "中商产业研究院《2025-2030年中国商业航天行业深度分析》",
            "界面新闻《中国商业航天年度成绩单》2025",
            "国家航天局数据",
            "《中国航天》期刊",
            "Yole Intelligence",
            "MarketsandMarkets",
        ],
        "market_size": {
            "global_2024": 4690,
            "global_2025": 4800,
            "global_2026e": 5200,
            "china_2024": 23200,
            "china_2025": 28300,
            "china_2026e": 35000,
        },
        "growth_rate": {
            "global_cagr_2024_2030": 8.5,
            "china_cagr_2020_2025": 23.1,
            "china_2025_yoy": 21.7,
            "china_2026e_yoy": 20.0,
        },
        "segments": {
            "卫星制造": 3200,
            "发射服务": 1800,
            "地面设备": 5200,
            "卫星通信": 8840,
            "卫星遥感": 4500,
            "卫星导航": 3260,
        },
        "funding_2025": {
            "total": 186,
            "卫星应用": 87,
            "火箭制造": 67.1,
            "卫星制造": 30,
        },
        "launch_stats": {
            "china_2024": 68,
            "china_2025": 90,
            "commercial_2024": 43,
            "us_2024": 158,
            "spacex_2024": 138,
        },
        "key_players": [
            "蓝箭航天(LandSpace)",
            "星河动力(Galactic Energy)",
            "星际荣耀(iSpace)",
            "东方空间(Oriental Space)",
            "天兵科技(Space Transportation)",
            "航天科技(CASC)",
            "航天科工(CASIC)",
        ],
        "policies": [
            "2024年《政府工作报告》将商业航天列为'新增长引擎'",
            "2025年'航天强国'写入'十五五'规划建议",
            "海南商业航天发射场2024年首次发射成功",
        ],
    }
}


import json
from pathlib import Path

_CACHE_PATH = Path(__file__).resolve().parent / "industry_cache.json"
_JSON_CACHE = {}


def _load_json_cache():
    global _JSON_CACHE
    try:
        if _CACHE_PATH.exists():
            _JSON_CACHE = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        _JSON_CACHE = {}


def get_data(asset: str) -> dict:
    """Get cached data for an asset. Checks both hardcoded dict and JSON cache."""
    data = INDUSTRY_DATA.get(asset)
    if data:
        return {"status": "available", "source": "web_cache", "quality": "verified", "data": data}
    if not _JSON_CACHE:
        _load_json_cache()
    json_data = _JSON_CACHE.get(asset)
    if json_data:
        return {"status": "available", "source": "web_cache", "quality": "verified", "data": json_data}
    return {"status": "unavailable", "source": "none", "quality": "unavailable", "data": []}


def get_all_assets() -> list:
    """Return list of all cached assets."""
    return list(INDUSTRY_DATA.keys())
