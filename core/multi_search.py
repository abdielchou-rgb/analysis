"""Multi-backend web search client (S1): unified failover chain.

Search backends are tried in order by query language:
- Chinese queries: bocha → tavily → keenable_public → keyless (DDG)
- English queries: exa → tavily → keenable_public → keyless (DDG)

Each backend is optional (key-gated) and fails silently to the next.
Results are normalized to a common shape:
    [{"url", "title", "content", "source_backend", "query_reason"}]

Usage:
    from core.multi_search import multi_search
    results = multi_search("宁德时代 财报", max_results=8, reason="财务")
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger("2hao.multi_search")

# ── Language detection ───────────────────────────────────────


def _is_chinese(query: str) -> bool:
    """Detect if query is predominantly Chinese (CJK chars)."""
    if not query:
        return False
    cjk = len(re.findall(r"[\u4e00-\u9fff]", query))
    return cjk >= max(2, len(query) * 0.3)


# ── Backend: Exa (semantic search, English-strong) ────────────


def _exa_search(query: str, max_results: int) -> Optional[list[dict]]:
    """Exa search API. Docs: https://docs.exa.ai. Requires EXA_API_KEY."""
    key = os.environ.get("EXA_API_KEY", "")
    if not key:
        return None
    try:
        import requests

        resp = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": key, "Content-Type": "application/json"},
            json={
                "query": query,
                "numResults": min(max_results, 10),
                "type": "auto",
                "contents": {"text": {"maxCharacters": 600}},
            },
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in data.get("results", []):
            text = r.get("text", "")
            if not text:
                continue
            results.append(
                {
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "content": text[:600],
                    "source_backend": "exa",
                }
            )
        logger.info("Exa: %d results for '%s'", len(results), query[:40])
        return results or None
    except Exception as e:
        logger.debug("Exa failed: %s", e)
        return None


# ── Backend: Bocha (Chinese search API) ──────────────────────


def _bocha_search(query: str, max_results: int) -> Optional[list[dict]]:
    """Bocha (博查) web search API — Chinese web coverage.
    Requires BOCHA_API_KEY. API: https://open.bochaai.com"""
    key = os.environ.get("BOCHA_API_KEY", "")
    if not key:
        return None
    try:
        import requests

        resp = requests.post(
            "https://api.bochaai.com/v1/web-search",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={"query": query, "count": min(max_results, 10), "summary": True},
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        # Bocha returns {code, data: {webPages: {value: [...]}}}
        pages = (data.get("data", {}) or {}).get("webPages", {}).get("value", [])
        for r in pages:
            content = r.get("summary", "") or r.get("snippet", "")
            if not content:
                continue
            results.append(
                {
                    "url": r.get("url", "") or r.get("link", ""),
                    "title": r.get("name", "") or r.get("title", ""),
                    "content": content[:600],
                    "source_backend": "bocha",
                }
            )
        logger.info("Bocha: %d results for '%s'", len(results), query[:40])
        return results or None
    except Exception as e:
        logger.debug("Bocha failed: %s", e)
        return None


# ── Backend: Keenable public (keyless) ────────────────────────


def _keenable_search(query: str, max_results: int) -> Optional[list[dict]]:
    """Keenable search — authenticated when KEENABLE_API_KEY present,
    keyless /public endpoint as fallback.
    Docs: https://docs.keenable.ai — POST https://api.keenable.ai/v1/search
    实测（2026-09-04）：payload 只接受 {"query"}；带 count 等额外参数会被拒。
    结果字段：title/url/description/snippet。"""
    import requests

    key = os.environ.get("KEENABLE_API_KEY", "")
    url = "https://api.keenable.ai/v1/search"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-API-Key"] = key  # authenticated lane
    payload = {"query": query}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=12)
        if resp.status_code in (401, 403, 400) and key:
            # Authenticated lane rejected — retry keyless
            resp = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=12,
            )
        resp.raise_for_status()
        data = resp.json()
        # Normalize: accept results/data arrays
        raw = data.get("results") or data.get("data") or []
        results = []
        for r in raw[:max_results]:
            if not isinstance(r, dict):
                continue
            content = r.get("snippet", "") or r.get("content", "") or r.get("description", "") or r.get("text", "")
            if not content:
                continue
            results.append(
                {
                    "url": r.get("url", "") or r.get("link", ""),
                    "title": r.get("title", "") or r.get("name", ""),
                    "content": content[:600],
                    "source_backend": "keenable",
                }
            )
        logger.info("Keenable: %d results for '%s'", len(results), query[:40])
        return results or None
    except Exception as e:
        logger.debug("Keenable failed: %s", e)
        return None


# ── Backend: Tavily (existing paid key) ───────────────────────


def _tavily_search(query: str, max_results: int, depth: str = "advanced") -> Optional[list[dict]]:
    """Existing Tavily backend (fallback position in chain)."""
    try:
        from core.web_intel import _get_tavily

        client = _get_tavily()
        if not client:
            return None
        resp = client.search(query=query, search_depth=depth, max_results=min(max_results, 5))
        results = []
        for r in resp.get("results", []):
            content = r.get("content", "")
            if not content:
                continue
            results.append(
                {
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "content": content[:600],
                    "source_backend": "tavily",
                }
            )
        return results or None
    except Exception as e:
        logger.debug("Tavily failed: %s", e)
        return None


# ── Backend: Bing CN (keyless, Chinese-strong) ───────────────


def _bing_cn_search(query: str, max_results: int) -> Optional[list[dict]]:
    """Bing CN direct scrape — keyless, no API needed, strong Chinese coverage.

    实测（2026-09-04）：cn.bing.com/search 稳定返回 10 条/查询，无反爬拦截。
    定位：bocha 的免费替代（bocha 需充值），中文链 keyless 层。
    """
    try:
        import requests
        from urllib.parse import quote
        from bs4 import BeautifulSoup

        resp = requests.get(
            f"https://cn.bing.com/search?q={quote(query)}",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                )
            },
            timeout=12,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for it in soup.select("li.b_algo")[:max_results]:
            a = it.select_one("h2 a")
            if not a:
                continue
            p = it.select_one(".b_caption p, p")
            snippet = p.get_text(strip=True) if p else ""
            if not snippet:
                continue
            results.append(
                {
                    "url": a.get("href", ""),
                    "title": a.get_text(strip=True),
                    "content": snippet[:600],
                    "source_backend": "bing_cn",
                }
            )
        logger.info("BingCN: %d results for '%s'", len(results), query[:40])
        return results or None
    except Exception as e:
        logger.debug("BingCN failed: %s", e)
        return None


# ── Backend: keyless DDG floor ────────────────────────────────


def _ddg_search(query: str, max_results: int) -> Optional[list[dict]]:
    """DuckDuckGo HTML keyless floor (same as last30days keyless lane)."""
    try:
        import requests
        from urllib.parse import quote

        resp = requests.get(
            f"https://html.duckduckgo.com/html/?q={quote(query)}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
        )
        resp.raise_for_status()
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select(".result")[:max_results]:
            a = r.select_one(".result__a")
            snippet = r.select_one(".result__snippet")
            if not a or not snippet:
                continue
            results.append(
                {
                    "url": a.get("href", ""),
                    "title": a.get_text(strip=True),
                    "content": snippet.get_text(strip=True)[:600],
                    "source_backend": "ddg",
                }
            )
        return results or None
    except Exception as e:
        logger.debug("DDG failed: %s", e)
        return None


# ── Unified multi-search entry ───────────────────────────────

# Chain order by language. Backends without keys fail fast (return None).
# BingCN (keyless, zh-strong) replaces bocha as the free zh primary;
# bocha auto-activates when funded.
CHAIN_ZH = ("bocha", "tavily", "keenable", "bing_cn", "ddg")
CHAIN_EN = ("exa", "tavily", "keenable", "bing_cn", "ddg")

# Name → module-level function (resolved at call time for testability)
_BACKENDS = {
    "bocha": "_bocha_search",
    "exa": "_exa_search",
    "tavily": "_tavily_search",
    "keenable": "_keenable_search",
    "bing_cn": "_bing_cn_search",
    "ddg": "_ddg_search",
}


def _resolve_backend(name: str):
    """Late-bind backend function by name (allows test patching)."""
    import core.multi_search as _ms

    return getattr(_ms, _BACKENDS[name], None)


def multi_search(
    query: str,
    max_results: int = 8,
    reason: str = "通用",
    depth: str = "advanced",
    prefer_zh: Optional[bool] = None,
) -> list[dict]:
    """Search the web via a failover chain of backends.

    Args:
        query: Search query (language auto-detected)
        max_results: Max results per backend
        reason: Query reason tag (propagated to results)
        depth: Tavily depth hint
        prefer_zh: Force language chain (None = auto-detect)

    Returns:
        Normalized results: [{url, title, content, source_backend, query_reason}]
        Empty list if all backends fail.
    """
    if not query:
        return []

    is_zh = prefer_zh if prefer_zh is not None else _is_chinese(query)
    chain = CHAIN_ZH if is_zh else CHAIN_EN

    for backend_name in chain:
        fn = _resolve_backend(backend_name)
        if fn is None:
            continue
        try:
            if backend_name == "tavily":
                results = fn(query, max_results, depth)
            else:
                results = fn(query, max_results)
            if results:
                for r in results:
                    r["query_reason"] = reason
                return results
        except Exception as e:
            logger.debug("Backend %s error: %s", backend_name, e)
            continue

    logger.warning("multi_search: all backends failed for '%s'", query[:40])
    return []


def available_backends() -> list[str]:
    """Report which backends are usable given current env keys."""
    usable = []
    if os.environ.get("BOCHA_API_KEY"):
        usable.append("bocha")  # activates when account funded
    if os.environ.get("EXA_API_KEY"):
        usable.append("exa")
    if os.environ.get("TAVILY_API_KEY"):
        usable.append("tavily")
    if os.environ.get("KEENABLE_API_KEY"):
        usable.append("keenable+auth")
    usable.append("keenable")  # keyless floor
    usable.append("bing_cn")  # keyless, zh-strong
    usable.append("ddg")  # keyless floor
    return usable
