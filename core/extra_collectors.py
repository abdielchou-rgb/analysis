# 雪球数据采集 + 招聘信号 + 数据源配置

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("2hao.extra_collectors")

# ── 环境变量注入 ──────────────────────────────────


def ensure_env():
    """从 .env 文件加载环境变量"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


ensure_env()

# ── Tavily 工具函数（直接使用配置好的key） ─────────

_TAVILY_CLIENT = None


def get_tavily():
    global _TAVILY_CLIENT
    if _TAVILY_CLIENT is not None:
        return _TAVILY_CLIENT
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        logger.warning("TAVILY_API_KEY not set")
        return None
    try:
        from tavily import TavilyClient

        _TAVILY_CLIENT = TavilyClient(api_key=key)
        return _TAVILY_CLIENT
    except Exception as e:
        logger.warning("Tavily init: %s", e)
        return None


def tavily_search(query: str, depth: str = "advanced", max_results: int = 5) -> list[dict]:
    """Tavily搜索（带故障保护）"""
    client = get_tavily()
    if not client:
        return []
    try:
        resp = client.search(query=query, search_depth=depth, max_results=max_results)
        results = resp.get("results", []) if isinstance(resp, dict) else []
        return results
    except Exception as e:
        logger.debug("Tavily search '%s': %s", query[:30], e)
        return []


# ── 雪球数据（通过Playwright） ─────────────────────


def fetch_xueqiu_sentiment(asset: str = "", asset_code: str = "") -> dict:
    """从雪球获取投资者情绪"""
    result = {"source": "xueqiu", "sentiment": "neutral", "signals": []}
    if not asset_code:
        return result
    # 使用Tavily搜索雪球相关讨论（比JS渲染稳定）
    query = f"xueqiu.com {asset} 讨论 分析 看好 看空 site:xueqiu.com"
    tavily_results = tavily_search(query, "basic", 5)
    texts = []
    for r in tavily_results:
        texts.append(r.get("content", "")[:300])
    full_text = " ".join(texts)
    # 情绪分析
    pos_count = sum(full_text.count(w) for w in ["看好", "买入", "加仓", "低估", "突破", "利好", "反转"])
    neg_count = sum(full_text.count(w) for w in ["看空", "卖出", "减仓", "高估", "破位", "利空", "崩盘"])
    if pos_count > neg_count * 1.5:
        result["sentiment"] = "positive"
    elif neg_count > pos_count * 1.5:
        result["sentiment"] = "negative"
    result["pos_signals"] = pos_count
    result["neg_signals"] = neg_count
    result["raw_count"] = len(tavily_results)
    return result


# ── 招聘信号（通过Boss直聘搜索） ─────────────────


def fetch_job_signals(company: str = "") -> dict:
    """从招聘数据判断公司扩张/收缩"""
    result = {"source": "job_search", "hiring_signal": "unknown", "job_count_est": 0, "trend": "stable"}
    if not company:
        return result
    # 使用Tavily搜索招聘信息
    query = f"{company} 招聘 2025 2026 岗位 扩张 裁员 site:zhipin.com OR site:lagou.com OR site:liepin.com"
    r = tavily_search(query, "basic", 5)
    texts = [item.get("content", "") for item in r]
    full = " ".join(texts)
    # 判断扩张还是收缩
    expand_words = ["大量招聘", "扩招", "新增岗位", "万人规模", "急聘", "高薪"]
    shrink_words = ["裁员", "优化", "缩减", "冻结招聘", "毕业", "赔偿"]
    exp_count = sum(full.count(w) for w in expand_words)
    shr_count = sum(full.count(w) for w in shrink_words)
    if exp_count > shr_count * 2:
        result["hiring_signal"] = "expanding"
        result["trend"] = "hiring"
    elif shr_count > exp_count * 2:
        result["hiring_signal"] = "shrinking"
        result["trend"] = "layoff"
    result["expand_signals"] = exp_count
    result["shrink_signals"] = shr_count
    result["raw_count"] = len(r)
    return result


# ── 综合数据采集 ──────────────────────────────────


def collect_all_extra(asset: str = "", asset_code: str = "", industry: str = "") -> dict:
    """运行所有额外数据集"""
    context = {}
    # 雪球情绪
    xq = fetch_xueqiu_sentiment(asset, asset_code)
    if xq.get("raw_count", 0) > 0:
        context["xueqiu"] = xq
        logger.info("Xueqiu: %s pos=%d neg=%d", xq["sentiment"], xq.get("pos_signals", 0), xq.get("neg_signals", 0))
    # 招聘信号
    company_name = asset.split()[0] if asset else ""
    js = fetch_job_signals(company_name)
    if js.get("raw_count", 0) > 0:
        context["job_signals"] = js
        logger.info("Job: %s trend=%s", company_name, js.get("trend", "?"))
    return context
