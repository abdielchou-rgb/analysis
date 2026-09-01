"""market_anchors.py — 市场规模外部权威锚点加载。

从 analysis_mixin._load_market_anchors 提取（C1 巨石拆解 2026-09-01）：
纯 I/O 工具函数，无 GateCheckResult 耦合。

用法:
    from pipeline.checks.market_anchors import load_market_anchors
    anchors = load_market_anchors(asset="柯力传感")
"""

from __future__ import annotations

import glob
import json
import logging
import os

logger = logging.getLogger("2hao.market_anchors")


def load_market_anchors(asset: str = "") -> dict:
    """加载市场规模外部权威锚点（R85）。

    优先从环境变量 ENRICH_ANCHOR_FILE 指定的 enrich JSON 读取；
    glob 兜底必须标的匹配（防跨标的污染）。
    返回 {"全球市场规模": {"unit": "亿美元", "values": {year: value}}, ...}；
    无可用锚点返回 {}。
    """
    cands = []
    env_path = os.environ.get("ENRICH_ANCHOR_FILE", "")
    if env_path and os.path.exists(env_path):
        cands.append((env_path, True))

    if asset:
        _bases = [os.getcwd()]
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if _root not in _bases:
            _bases.append(_root)
        for _b in _bases:
            for _sub in ("data", "output"):
                _pat = os.path.join(_b, _sub, "*_enrich*.json")
                try:
                    _ms = sorted(glob.glob(_pat), key=os.path.getmtime, reverse=True)
                    cands.extend((_p, False) for _p in _ms[:3])
                except Exception:
                    pass

    def _asset_match(path_or_str: str, payload_asset: str = "") -> bool:
        a, b = asset, (payload_asset or "").strip()
        if not a:
            return False
        hay = path_or_str.replace("\\", "/").lower()
        if a.lower() in hay:
            return True
        return bool(b) and (a in b or b in a)

    for p, trusted in cands:
        try:
            with open(p, encoding="utf-8") as fh:
                enrich = json.load(fh)
            if not trusted and not _asset_match(
                os.path.basename(p), str(enrich.get("asset", "")) if isinstance(enrich, dict) else ""
            ):
                continue
            items = enrich.get("items", []) if isinstance(enrich, dict) else []
            out = {}
            for it in items:
                if not isinstance(it, dict):
                    continue
                key = it.get("key") or it.get("field") or ""
                val = it.get("data") if it.get("data") is not None else it.get("value")
                _unit = it.get("unit", "")
                if key == "fig_market_size_global" and isinstance(val, dict):
                    out["全球市场规模"] = {
                        "unit": _unit or "亿美元",
                        "values": {str(k): v for k, v in val.items() if isinstance(v, (int, float))},
                    }
                elif key == "fig_market_size_china" and isinstance(val, dict):
                    out["中国市场规模"] = {
                        "unit": _unit or "亿元",
                        "values": {str(k): v for k, v in val.items() if isinstance(v, (int, float))},
                    }
            if out:
                return out
        except Exception:
            continue
    return {}
