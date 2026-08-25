# -*- coding: utf-8 -*-
"""macro_context.py — K-10 宏观背景数据注入器。

从 data/global_macro.json 读取 Fed 利率/CPI/GDP/美元指数等
宏观数据，生成写作 prompt 的宏观背景段。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_FILE = Path(__file__).resolve().parent.parent / "data" / "global_macro.json"

_LABEL = {
    "fed_rate": "美联储联邦基金利率",
    "us_nonfarm": "美国非农就业",
    "us_cpi_yoy": "美国CPI同比",
    "us_gdp_growth": "美国GDP增速",
    "us10y_yield": "10年期美债收益率",
    "dollar_index": "美元指数",
}


@lru_cache(maxsize=1)
def load() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def block() -> str:
    """生成宏观背景段（≤300 字）。无数据返回空串。"""
    d = load()
    if not d or len(d) < 3:
        return ""
    lines = ["## [宏观环境背景] 以下为最新宏观数据快照，供分析框架参考："]
    for key, label in _LABEL.items():
        v = d.get(key)
        if v is not None:
            lines.append(f"  {label}: {v}")
    src = d.get("source", "")
    if src:
        lines.append(f"  数据来源: {src}")
    lines.append("  请在分析利率敏感、出口敞口或估值折现率时引用上述数据。")
    return "\n".join(lines) + "\n"
