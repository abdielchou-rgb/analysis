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
    """Keenable public search (keyless /public endpoint).
    Docs: https://docs.keenable.ai — POST https://api.keenable.ai/v1/search"""
    try:
        import requests

        resp = requests.post(
            "https://api.keenable.ai/v1/search",
            headers={"Content-Type": "application/json"},
            json={"query": query, "count": min(max_results, 8)},
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        # Normalize: accept both {"results": [...]} and {"data": [...]}
        raw = data.get("results") or data.get("data") or []
        results = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            content = r.get("content", "") or r.get("snippet", "") or r.get("text", "")
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
CHAIN_ZH = ("bocha", "tavily", "keenable", "ddg")
CHAIN_EN = ("exa", "tavily", "keenable", "ddg")

# Name → module-level function (resolved at call time for testability)
_BACKENDS = {
    "bocha": "_bocha_search",
    "exa": "_exa_search",
    "tavily": "_tavily_search",
    "keenable": "_keenable_search",
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
        usable.append("bocha")
    if os.environ.get("EXA_API_KEY"):
        usable.append("exa")
    if os.environ.get("TAVILY_API_KEY"):
        usable.append("tavily")
    usable.append("keenable")  # keyless
    usable.append("ddg")  # keyless
    return usable
