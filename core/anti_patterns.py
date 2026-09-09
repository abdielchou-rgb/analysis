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
    """返回命中 [{pattern, count}]。仅统计无量化支撑的裸表述。

    2026-09-09（Gate 0.95 提分）：豁免框架应用句——"用【XX框架】分析…护城河…"
    是 Evidence-Grounded Writing 的合法产出，量化常在下一小句（"具体结论1：…"），
    80 字窗口被句号截断导致误报（实测 3 处误伤全部是带量化结论的合格句）。
    规则：匹配点前 30 字内出现"【"框架标记，或后 12 字内出现"：+数字开头结论"，
    一律跳过。
    """
    import re

    hits = []
    for p in patterns():
        raw = p.get("regex")
        if not raw:
            continue
        try:
            matches = list(re.finditer(raw, text))
        except Exception:
            continue
        n = 0
        for m in matches:
            before = text[max(0, m.start() - 30) : m.start()]
            after = text[m.end() : m.end() + 12]
            # 豁免 1：框架应用标记（"用【经济护城河分析框架】分析"）
            if "【" in before:
                continue
            # 豁免 2：结论句式紧随其后（"：具体结论…" / "——…" 破折号量化）
            if re.match(r"^[：:—-]", after):
                continue
            # 豁免 3：计数型量化前缀（"三重护城河""四大壁垒"——枚举即量化）
            if re.search(r"(?:三重|双重|多重|四大|五大|六大|三大|单一)$", before[-8:]):
                continue
            n += 1
        if n:
            hits.append({"pattern": p.get("name", "?"), "count": n})
    return hits


def re_findall(raw: str, text: str):
    import re

    return re.findall(raw, text)
