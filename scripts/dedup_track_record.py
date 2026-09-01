#!/usr/bin/env python3
"""dedup_track_record.py — track_record.json 去重 + time_horizon 回填"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACK_FILE = ROOT / "core" / "data" / "forward_picks" / "track_record.json"

# 默认时间跨度映射（根据 bold_call 关键词推断）
HORIZON_KEYWORDS = {
    "12m": ["12个月", "12m", "一年", "中长期", "年度"],
    "6m": ["6个月", "6m", "半年", "中期"],
    "3m": ["3个月", "3m", "季度", "短期"],
    "24m": ["24个月", "24m", "两年", "长期"],
}


def infer_time_horizon(pred: dict) -> str:
    """从 bold_call 和 context 推断时间跨度。"""
    if pred.get("time_horizon") and pred["time_horizon"] != "unknown":
        return pred["time_horizon"]
    bold = (pred.get("bold_call", "") + " " + pred.get("context", "")).lower()
    for horizon, keywords in HORIZON_KEYWORDS.items():
        for kw in keywords:
            if kw in bold:
                return horizon
    # 默认：listed_company=12m, unlisted=24m, industry=12m
    rtype = pred.get("report_type", "")
    if "unlisted" in rtype:
        return "24m"
    return "12m"


def dedup(predictions: list[dict]) -> list[dict]:
    """去重：同一 (asset, bold_call[:80], made_date) 保留最新一条。"""
    seen = {}
    for p in predictions:
        key = (
            p.get("asset", ""),
            (p.get("bold_call", "") or "")[:80],
            p.get("made_date", ""),
        )
        existing = seen.get(key)
        if existing is None:
            seen[key] = p
        else:
            # 保留 updated_at 更大的
            if (p.get("updated_at") or p.get("made_date", "")) > (
                existing.get("updated_at") or existing.get("made_date", "")
            ):
                seen[key] = p
    return list(seen.values())


def backfill_time_horizon(predictions: list[dict]) -> int:
    """回填 unknown time_horizon，返回修改数。"""
    count = 0
    for p in predictions:
        if not p.get("time_horizon") or p["time_horizon"] == "unknown":
            new_h = infer_time_horizon(p)
            if new_h != "unknown":
                p["time_horizon"] = new_h
                count += 1
    return count


def main():
    if not TRACK_FILE.exists():
        print(f"Track record not found: {TRACK_FILE}")
        sys.exit(1)

    with open(TRACK_FILE, encoding="utf-8") as f:
        data = json.load(f)

    preds = data.get("predictions", [])
    original_count = len(preds)

    # 1. 去重
    deduped = dedup(preds)
    removed = original_count - len(deduped)

    # 2. 回填 time_horizon
    filled = backfill_time_horizon(deduped)

    # 3. 统计
    horizons = {}
    for p in deduped:
        h = p.get("time_horizon", "unknown")
        horizons[h] = horizons.get(h, 0) + 1

    # 4. 保存
    data["predictions"] = deduped
    with open(TRACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Dedup: {original_count} -> {len(deduped)} (removed {removed})")
    print(f"Time horizon backfill: {filled} records")
    print(f"Horizon distribution: {horizons}")


if __name__ == "__main__":
    main()
