# -*- coding: utf-8 -*-
"""industry_router.py — M2 行业方法路由器（行业 → 框架组合/红线/跳过集）。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_ROUTE_FILE = Path(__file__).resolve().parent.parent / "config" / "methodology_router.yaml"

# 框架名 → 注入器变量名（framework-ish 子集；其余注入器不受路由影响）
FRAMEWORK_INJECTORS = {
    "bottleneck": "bn_str",
    "profit_pool": None,  # 走 methodology_rules 主题，非独立注入器
    "signal_chain": None,  # 同上（topic）+ tool_modules
    "technology_roadmap": None,
    "triangulation": "tri_str",
    "valuation_crosscheck": "vc_str",
    "global_benchmark": "bm_str",
    "catalyst_timeline": "cat_str",
    "reference_class": None,
    "bull_bear_matrix": "bb_str",
}


@lru_cache(maxsize=1)
def _routes() -> dict:
    try:
        return yaml.safe_load(_ROUTE_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def guess_industry(asset: str, data_context: dict | None = None) -> str:
    """按资产名与 biz_model.industry_tags 关键词猜测行业键。"""
    text = asset or ""
    dc = data_context or {}
    biz = dc.get("biz_model") if isinstance(dc, dict) else {}
    tags = []
    if isinstance(biz, dict):
        tags = biz.get("industry_tags") or []
    text = f"{text} {' '.join(str(t) for t in tags)}".lower()
    for key, cfg in _routes().items():
        if key == "default":
            continue
        for kw in cfg.get("keywords", []):
            if str(kw).lower() in text:
                return key
    return "default"


def route(industry: str | None = None) -> dict:
    """返回该行业的路由配置；未命中返回 default 配置。"""
    rts = _routes()
    return (
        rts.get(industry)
        or rts.get("default")
        or {
            "primary": ["methodology_rules"],
            "verify": [],
            "oppose": [],
            "injector_skip": [],
        }
    )


def route_injector_skip(asset: str, data_context: dict | None = None) -> set[str]:
    """该行业应禁用的注入器变量集合。"""
    ind = guess_industry(asset, data_context)
    cfg = route(ind)
    skip = set()
    for fw in cfg.get("injector_skip", []) or []:
        var = FRAMEWORK_INJECTORS.get(fw)
        if var:
            skip.add(var)
    # 未列入 primary/verify/oppose 的框架型注入器：非 default 行业时降权关闭，
    # 让"主框架"真正主导（default 保持全开）。
    if ind != "default":
        allowed_fw = set(cfg.get("primary", []) + cfg.get("verify", []) + cfg.get("oppose", []))
        for fw, var in FRAMEWORK_INJECTORS.items():
            if var and fw not in allowed_fw:
                skip.add(var)
    return {s for s in skip if s}
