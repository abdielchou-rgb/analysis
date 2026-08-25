# -*- coding: utf-8 -*-
"""S4 节奏模板加载器。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_FILE = Path(__file__).resolve().parent.parent / "config" / "rhythm_patterns.yaml"


@lru_cache(maxsize=1)
def patterns() -> list[dict]:
    try:
        d = yaml.safe_load(_FILE.read_text(encoding="utf-8")) or []
        return d if isinstance(d, list) else []
    except Exception:
        return []


def directive_for(group_name: str, dims: list[str]) -> str:
    """按组名/维度关键词返回节奏指令（首条命中）。"""
    text = f"{group_name} {' '.join(dims)}".lower()
    for p in patterns():
        for kw in p.get("match_keywords", []):
            if str(kw).lower() in text:
                return str(p.get("directive", ""))
    return ""
