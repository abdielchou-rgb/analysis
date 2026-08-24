# -*- coding: utf-8 -*-
"""methodology_confidence.py — 方法论置信度（预测账本 → 写作先验）。

P3-B 落地：把 prediction_loop 的历史验证结果聚合为"某类判断的历史命中率"，
以先验提示注入写作 prompt——让 LLM 知道本系统过往同类判断的兑现情况。

数据源：data/predictions.json（prediction_loop v2 账本）。
无已验证记录时返回空串（不虚构先验）。
"""

from __future__ import annotations

import json
from pathlib import Path

_DB = Path(__file__).resolve().parent.parent / "data" / "predictions.json"

_KIND_LABEL = {
    "rating": "评级方向",
    "target_price": "目标价",
    "eps_forecast": "EPS 预测",
}


def _load() -> list[dict]:
    try:
        d = json.loads(_DB.read_text(encoding="utf-8"))
        return d.get("predictions", [])
    except Exception:
        return []


def confidence_stats(kind: str | None = None, text_hint: str = "") -> dict:
    """统计命中分布。kind 过滤类型；text_hint 过滤语句关键词（如行业词）。

    返回 {total, verified, hits(偏差≤10%), hit_rate} 或全零。
    """
    preds = _load()
    rows = []
    for p in preds:
        if kind and p.get("statement", "").startswith(f"[{kind}]"):
            pass
        elif kind:
            continue
        if text_hint and text_hint not in p.get("statement", ""):
            continue
        rows.append(p)
    verified = [p for p in rows if p.get("verified") and p.get("deviation_pct") is not None]
    hits = [p for p in verified if abs(p["deviation_pct"]) <= 10.0]
    return {
        "total": len(rows),
        "verified": len(verified),
        "hits": len(hits),
        "hit_rate": round(len(hits) / len(verified), 2) if verified else 0.0,
    }


def confidence_block(asset: str = "", kinds=("rating", "target_price", "eps_forecast")) -> str:
    """生成写作先验提示块；无已验证历史则返回空串。"""
    # 关联度匹配：优先精确 code，其次语句含资产名
    preds = _load()
    asset_preds = [p for p in preds if p.get("code") == asset or asset in p.get("statement", "")]
    scope_note = f"（标的：{asset}）" if asset_preds else ""
    lines = []
    for kind in kinds:
        st = confidence_stats(kind=kind)
        if st["verified"] >= 3:  # 样本不足不出先验
            label = _KIND_LABEL.get(kind, kind)
            tone = "良好" if st["hit_rate"] >= 0.6 else "一般" if st["hit_rate"] >= 0.4 else "偏弱"
            lines.append(
                f"- {label}：历史已验证 {st['verified']} 条，±10% 命中率 "
                f"{st['hit_rate']:.0%}（{tone}）——请据此调整论证强度与证伪条件具体性"
            )
    if not lines:
        return ""
    head = f"## [方法论置信度先验{scope_note}] 本系统同类判断的历史兑现情况："
    return head + "\n" + "\n".join(lines) + "\n"
