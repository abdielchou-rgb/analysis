# -*- coding: utf-8 -*-
"""macro_context.py — K-10 宏观背景数据注入器。

从 data/global_macro.json 读取宏观数据，只提取每个指标的**最新值**，
生成紧凑的宏观背景段。修复前版本把整个时序列表 str() 后注入 prompt
（156,430 chars / ~87k tokens）——严重超出预算。
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
    "us10y_yield": "10Y美债收益率",
    "dollar_index": "美元指数",
}


@lru_cache(maxsize=1)
def load() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest(v) -> tuple[str, str]:
    """从时序数据中提取最新值和日期。支持 list[dict] 和标量两种格式。"""
    if isinstance(v, list) and v:
        latest = v[-1]
        if isinstance(latest, dict):
            date = str(latest.get("date", ""))
            val = latest.get("value", "")
            return str(val), date
        return str(latest), ""
    if isinstance(v, (int, float)):
        return str(v), ""
    return str(v), ""


def block() -> str:
    """生成宏观背景段（≤300 字）。无数据返回空串。"""
    d = load()
    if not d or len(d) < 3:
        return ""
    lines = ["## [宏观环境背景] 最新数据快照："]
    for key, label in _LABEL.items():
        raw = d.get(key)
        if raw is None:
            continue
        val, date = _latest(raw)
        if date:
            lines.append(f"  {label}: {val} ({date})")
        else:
            lines.append(f"  {label}: {val}")
    src = d.get("source", "")
    if src:
        lines.append(f"  来源: {src}")
    lines.append("  请在分析利率敏感、出口敞口或估值折现率时引用上述数据。")
    result = "\n".join(lines) + "\n"
    # 安全阀：无论如何不超过 600 chars
    return result[:600] + "\n" if len(result) > 600 else result
