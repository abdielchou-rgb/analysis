# -*- coding: utf-8 -*-
"""M6 伪框架黑名单 — 不可证伪话术拦截。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_FILE = Path(__file__).resolve().parent.parent / "data" / "anti_patterns.yaml"


@lru_cache(maxsize=1)
def patterns() -> list[dict]:
    try:
        d = yaml.safe_load(_FILE.read_text(encoding="utf-8")) or []
        return d if isinstance(d, list) else []
    except Exception:
        return []


def scan(text: str) -> list[dict]:
    """返回命中 [{pattern, count}]。仅统计无量化支撑的裸表述。"""
    hits = []
    for p in patterns():
        raw = p.get("regex")
        if not raw:
            continue
        try:
            n = len(re_findall(raw, text))
        except Exception:
            continue
        if n:
            hits.append({"pattern": p.get("name", "?"), "count": n})
    return hits


def re_findall(raw: str, text: str):
    import re

    return re.findall(raw, text)
