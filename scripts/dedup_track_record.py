#!/usr/bin/env python3
"""dedup_track_record.py — track_record.json 保守去重 + id 唯一化 + time_horizon 回填

2026-09-07 T3 改写：
- 旧 dedup 以 (asset, bold_call[:80], made_date) 为键合并，会把同报告内多个
  独立 Bold Call（碰巧共享长前缀）误合并。新版只在 asset/made_date/direction/
  time_horizon/target_price 全等、且文本完全相等或共享 ≥60 字符前缀时判为重复，
  保留首条。
- 旧 id 只到分钟精度，同分钟多条记录撞 id，导致 resolve 只结算第一行。
  新增 uniquify_ids：对共享 id 的记录追加内容摘要，恢复一一结算能力。
- 默认 dry-run，--apply 才写盘；写盘仍走 TrackRecordManager._save (SSOT 单写)。
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
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


def _norm(text) -> str:
    return " ".join((text or "").split())


def _same_call(a: dict, b: dict) -> bool:
    """语义重复判定（保守）：关键字段全等 + 文本相等或共享 ≥60 字符前缀。"""
    for field in ("asset", "made_date", "direction", "time_horizon", "target_price"):
        if (a.get(field) or "") != (b.get(field) or ""):
            return False
    ta, tb = _norm(a.get("bold_call")), _norm(b.get("bold_call"))
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    n = min(len(ta), len(tb))
    if n < 60:
        return False
    return ta[:60] == tb[:60]


def dedup(predictions: list[dict]) -> tuple[list[dict], int]:
    """保守去重：保留同批首次出现的记录，返回 (去重后列表, 删除数)。"""
    kept = []
    removed = 0
    for p in predictions:
        if any(_same_call(p, q) for q in kept):
            removed += 1
            continue
        kept.append(p)
    return kept, removed


def _content_digest(pred: dict) -> str:
    payload = "\x1f".join(
        str(pred.get(k, "")) for k in ("asset", "bold_call", "direction", "time_horizon", "made_date")
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def uniquify_ids(predictions: list[dict]) -> int:
    """让每条记录 id 唯一：共享 id 的记录追加内容摘要（历史分钟级撞 id 修复）。"""
    counts = collections.Counter(p.get("id") for p in predictions)
    used = set()
    changed = 0
    for p in predictions:
        pid = p.get("id") or ""
        if counts.get(pid, 0) <= 1:
            if pid not in used:
                used.add(pid)
            continue
        base = f"{pid}_{_content_digest(p)}"
        candidate = base
        n = 1
        while candidate in used:
            candidate = f"{base}_{n}"
            n += 1
        p["id"] = candidate
        used.add(candidate)
        changed += 1
    return changed


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Conservative track_record cleanup")
    parser.add_argument("--apply", action="store_true", help="写入磁盘（默认只预览）")
    parser.add_argument("--track-record", default=str(TRACK_FILE))
    args = parser.parse_args()

    track_file = Path(args.track_record)
    if not track_file.exists():
        print(f"Track record not found: {track_file}")
        sys.exit(1)

    with open(track_file, encoding="utf-8") as f:
        data = json.load(f)

    preds = data.get("predictions", [])
    original_count = len(preds)

    # 1. 保守去重
    deduped, removed = dedup(preds)

    # 2. id 唯一化
    reid = uniquify_ids(deduped)

    # 3. 回填 time_horizon
    filled = backfill_time_horizon(deduped)

    # 4. 统计
    horizons = collections.Counter(p.get("time_horizon", "unknown") for p in deduped)
    dup_ids = sum(1 for c in collections.Counter(p.get("id") for p in deduped).values() if c > 1)

    print(f"Rows: {original_count} -> {len(deduped)} (removed {removed})")
    print(f"Re-id collision rows: {reid}")
    print(f"Time horizon backfill: {filled}")
    print(f"Remaining duplicate ids: {dup_ids}")
    print(f"Horizon distribution: {dict(horizons)}")

    if not args.apply:
        print("Dry run — pass --apply to write.")
        return

    # SSOT (2026-09-07): 唯一写路径 = TrackRecordManager, 禁止裸 json.dump
    from core.tools.track_record import Prediction, TrackRecord, TrackRecordManager

    valid_fields = set(Prediction.__dataclass_fields__)
    data["predictions"] = [{k: v for k, v in p.items() if k in valid_fields} for p in deduped]
    manager = TrackRecordManager(storage_path=str(track_file))
    manager.record = TrackRecord(
        analyst_name=data.get("analyst_name", "2号分析师"),
        predictions=[Prediction(**p) for p in data["predictions"]],
    )
    manager._save()
    print("Written via TrackRecordManager SSOT facade.")


if __name__ == "__main__":
    main()
