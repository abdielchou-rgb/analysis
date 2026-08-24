# Web Intelligence Layer — 用 Tavily + Playwright 获取多维度数据
# 补 akshare 的短板: 定性数据、行业动态、竞争情报、国际视角

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.web_intel")

try:
    from tavily import TavilyClient

    _HAS_TAVILY = True
except ImportError:
    _HAS_TAVILY = False

try:
    import requests
    from bs4 import BeautifulSoup

    _HAS_SCRAPE = True
except ImportError:
    _HAS_SCRAPE = False

try:
    import yfinance as yf

    _HAS_YF = True
except ImportError:
    _HAS_YF = False


# ── 数据分类 ──────────────────────────────────────


@dataclass
class WebIntelResult:
    """网络智能采集结果"""

    news: list = field(default_factory=list)  # 新闻动态
    industry: list = field(default_factory=list)  # 行业信息
    competitors: list = field(default_factory=list)  # 竞争情报
    catalysts: list = field(default_factory=list)  # 催化刑事件
    risks: list = field(default_factory=list)  # 风险信号
    macro: list = field(default_factory=list)  # 宏观政策
    raw_sources: list = field(default_factory=list)  # 原始来源记录
    errors: list = field(default_factory=list)  # 错误记录
    search_count: int = 0


# ── Tavilly 多轮搜索 ──────────────────────────────


def _get_tavily() -> TavilyClient | None:
    if not _HAS_TAVILY:
        return None
    import os

    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        logger.debug("Tavily: no API key")
        return None
    try:
        return TavilyClient(api_key=key)
    except Exception as e:
        logger.debug("Tavily init: %s", e)
        return None


def search_tavily_multi(client: TavilyClient, queries: list[dict]) -> list[dict]:
    """并行多轮Tavily搜索，每次用不同查询"""
    if not client:
        return []
    all_results = []
    seen_urls = set()
    plan = queries if queries else []
    for pq in plan[:6]:  # 最多6轮，节省API额度
        q = pq.get("query", "")
        depth = pq.get("depth", "advanced")
        max_r = min(pq.get("max_results", 5), 5)
        reason = pq.get("reason", "通用")
        if not q:
            continue
        try:
            resp = client.search(query=q, search_depth=depth, max_results=max_r)
            results = resp.get("results", []) if isinstance(resp, dict) else []
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(
                        {
                            "url": url,
                            "title": r.get("title", ""),
                            "content": r.get("content", "")[:500],
                            "query_reason": reason,
                        }
                    )
            logger.info("  Tavily [%s]: %d results for '%s'", reason, len(results), q[:40])
        except Exception as e:
            logger.debug("Tavily query '%s' failed: %s", q[:30], e)
    return all_results


# ── Playwright 定向抓取 ─────────────────────────

# 金融数据目标网站（免费可访问）
TARGET_SITES = {
    "eastmoney": {
        "name": "东方财富",
        "url_template": "https://quote.eastmoney.com/{code}.html",
        "type": "financial_portal",
    },
    "cls": {
        "name": "财联社",
        "url_template": "https://www.cls.cn/searchPage?keyword={asset}&type=all",
        "type": "news",
    },
    "10jqka": {
        "name": "同花顺",
        "url_template": "https://stockpage.10jqka.com.cn/{code}/",
        "type": "financial_portal",
    },
}


def scrape_simple(url: str) -> str | None:
    """简单HTTP抓取（无需JS渲染）"""
    if not _HAS_SCRAPE:
        return None
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # 提取文本
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:3000]
    except Exception as e:
        logger.debug("Scrape %s: %s", url[:40], e)
        return None


# ── yfinance 国际视角 ─────────────────────────────


def yfinance_intel(asset_code: str = "") -> dict:
    """yfinance 提供的额外数据（无法从akshare获得）"""
    result = {}
    if not _HAS_YF or not asset_code:
        return result
    try:
        # 转yfinance ticker
        code = asset_code[:6]
        if code.startswith(("6", "9")):
            ticker = f"{code}.SS"
        elif code.startswith(("0", "3")):
            ticker = f"{code}.SZ"
        else:
            return result
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        # 提取国际视角数据
        result["short_ratio"] = info.get("shortRatio")
        result["recommendation"] = info.get("recommendationKey")
        result["target_mean"] = info.get("targetMeanPrice")
        result["target_high"] = info.get("targetHighPrice")
        result["target_low"] = info.get("targetLowPrice")
        result["number_of_analysts"] = info.get("numberOfAnalystOpinions")
        result["beta"] = info.get("beta")
        result["sector"] = info.get("sector")
        result["industry"] = info.get("industry")
        result["full_time_employees"] = info.get("fullTimeEmployees")
        result["country"] = info.get("country")
        # 财报日期
        result["earnings_date"] = str(info.get("earningsDate", ""))[:20]
        # 国际同行的ESG评分
        result["esg_score"] = info.get("esgScore")
        # 剔除 None
        result = {k: v for k, v in result.items() if v is not None}
    except Exception as e:
        logger.debug("yfinance intel: %s", e)
    return result


# ── 主入口 ──────────────────────────────────────


def collect_all(
    asset: str = "", asset_code: str = "", industry: str = "", report_type: str = "listed_company"
) -> WebIntelResult:
    """运行所有网络智能采集"""
    result = WebIntelResult()
    result.search_count = 0

    # 1. Tavily多轮搜索
    client = _get_tavily()
    if client:
        from core.search_planner import plan_macro_queries, plan_queries

        # 资产查询
        queries = plan_queries(asset, report_type, industry)
        # 宏观查询
        macro_q = plan_macro_queries()
        all_results = search_tavily_multi(client, queries + macro_q)
        result.search_count = len(all_results)
        # 按reason分类
        for r in all_results:
            reason = r.get("query_reason", "通用")
            if "SAC维度: catalyst" in reason:
                result.catalysts.append(r)
            elif "SAC维度: falsification" in reason:
                result.risks.append(r)
            elif "国际" in reason or "宏观" in reason:
                result.macro.append(r)
            elif "行业" in reason:
                result.industry.append(r)
            elif "竞争" in reason:
                result.competitors.append(r)
            else:
                result.news.append(r)
            result.raw_sources.append(r.get("url", ""))
        logger.info("WebIntel Tavily: %d results from %d queries", len(all_results), len(queries) + len(macro_q))

    # 2. yfinance国际数据
    yf_data = yfinance_intel(asset_code)
    if yf_data:
        result.raw_sources.append(f"yfinance:{asset_code}")
        logger.info("WebIntel yfinance: %d fields", len(yf_data))
        # yf_data 通过 context 传递
        result.raw_sources.append(json.dumps(yf_data, ensure_ascii=False)[:500])

    return result


def intel_to_context(result: WebIntelResult) -> dict:
    """WebIntelResult → context dict（供pipeline使用）"""
    ctx = {}
    ctx["web_news"] = [r["title"] for r in result.news[:5]]
    ctx["web_industry"] = [r["title"] for r in result.industry[:5]]
    ctx["web_catalysts"] = [r["title"] for r in result.catalysts[:5]]
    ctx["web_risks"] = [r["title"] for r in result.risks[:5]]
    ctx["web_macro"] = [r["title"] for r in result.macro[:5]]
    ctx["web_search_count"] = result.search_count
    # 摘要（给LLM用）
    summaries = []
    for r in result.news[:3]:
        summaries.append(f"[新闻] {r['title']}: {r['content'][:200]}")
    for r in result.industry[:2]:
        summaries.append(f"[行业] {r['title']}: {r['content'][:200]}")
    for r in result.catalysts[:2]:
        summaries.append(f"[催化剂] {r['title']}: {r['content'][:200]}")
    ctx["web_summary"] = "\n".join(summaries)
    return ctx
