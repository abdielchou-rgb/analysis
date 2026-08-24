"""V51 Report Cache — scaffold versioning + historical diff.

共识四 (P1, 圆桌): 报告版本化 + 历史 diff。
当同类报告（相同 asset + report_type）已存在时：
  - 比较新旧 scaffold 的 thesis 和 evidence_ids
  - 只重写被数据更新影响到的章节
  - 保持已验证的判断不变

Architecture:
  report_cache.json  ← index of all past scaffolds
       │
  ReportCache.find_existing(asset, report_type)
       │
  ReportCache.diff(new_scaffold, old_scaffold)
       │
  → List of changed section_ids + unchanged section_ids
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.models import ArgumentScaffold, ArgumentSection, WritingBrief

logger = logging.getLogger("v51.report_cache")

CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_FILE = CACHE_DIR / "report_cache.json"


def _get_cache() -> dict:
    """Load cache from disk."""
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Cache load failed: {e}")
    return {"version": "V51.1", "reports": {}}


def _save_cache(cache: dict):
    """Persist cache to disk."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _section_fingerprint(section: ArgumentSection) -> str:
    """Create a hash of a section's thesis + evidence_ids + counter."""
    content = f"{section.thesis}|{','.join(section.evidence_ids)}|{section.counter_thesis}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def _scaffold_fingerprint(scaffold: ArgumentScaffold) -> str:
    """Create a hash of the full scaffold."""
    parts = [scaffold.core_disagreement.get("our_view", "")]
    for s in scaffold.sections:
        parts.append(_section_fingerprint(s))
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]


class ReportCache:
    """Persistent cache of report scaffolds for diff-based regeneration."""

    @staticmethod
    def find_existing(asset_code: str,
                       report_type: str) -> Optional[dict]:
        """Find most recent cached scaffold for an asset + type.

        Returns: {
          "scaffold": {...},  # serialized ArgumentScaffold
          "brief": {...},     # serialized WritingBrief
          "created_at": "...",
          "fingerprint": "..."
        } or None.
        """
        cache = _get_cache()
        key = f"{asset_code}:{report_type}"
        entries = cache.get("reports", {}).get(key, [])
        if entries:
            return max(entries, key=lambda e: e.get("created_at", ""))
        return None

    @staticmethod
    def save(scaffold: ArgumentScaffold, brief: WritingBrief):
        """Save scaffold to cache."""
        cache = _get_cache()
        key = f"{brief.asset_code or brief.asset}:{brief.report_type.value if brief.report_type else 'unknown'}"

        entry = {
            "fingerprint": _scaffold_fingerprint(scaffold),
            "created_at": scaffold.created_at or datetime.now().isoformat(),
            "brief_id": scaffold.brief_id,
            "brief": brief.to_dict() if hasattr(brief, "to_dict") else {},
            "scaffold": {
                "title": scaffold.title,
                "core_disagreement": scaffold.core_disagreement,
                "data_gaps": scaffold.data_gaps,
                "sections": [
                    {
                        "section_id": s.section_id,
                        "title": s.title,
                        "thesis": s.thesis,
                        "counter_thesis": s.counter_thesis,
                        "evidence_ids": s.evidence_ids,
                        "counter_evidence_ids": s.counter_evidence_ids,
                        "data_gaps": s.data_gaps,
                        "fingerprint": _section_fingerprint(s),
                    }
                    for s in scaffold.sections
                ],
            },
        }

        cache.setdefault("reports", {}).setdefault(key, []).append(entry)
        # Keep only last 5 per key
        cache["reports"][key] = cache["reports"][key][-5:]
        _save_cache(cache)
        logger.info(f"Cached scaffold {key} ({entry['fingerprint']})")

    @staticmethod
    def get_same_sector_reports(asset: str, report_type: str = "", limit: int = 5) -> list:
        """R75（2026-08-05 Phase 4）：获取同赛道/同业的历史报告摘要。

        油位v6审计发现：柯力v5和油位v6属于同一传感器赛道，但彼此完全不知对方存在。
        本方法从缓存中查与当前标的同行业/同赛道的报告，
        返回简化的摘要（asset/评级/目标价/核心判断），供写作时对照。
        """
        cache = _get_cache()
        reports = cache.get("reports", {})
        results = []

        # 提取行业关键词（从asset名或report_type推断）
        sector_keywords = set()
        asset_lower = (asset or "").lower()
        for kw in ["传感器", "sensor", "芯片", "半导体", "机器人", "新能源", "电池",
                    "医药", "消费", "化工", "汽车", "光伏", "锂电", "液位", "油位",
                    "气体", "磁致", "雷达"]:
            if kw.lower() in asset_lower:
                sector_keywords.add(kw)

        for key, entries in reports.items():
            if not entries:
                continue
            latest = max(entries, key=lambda e: e.get("created_at", ""))
            brief = latest.get("brief", {})
            # 检查行业匹配
            brief_asset = str(brief.get("asset", "") or latest.get("asset", ""))
            brief_type = str(brief.get("report_type", latest.get("report_type", "")))
            # 排除自己
            if asset and asset in brief_asset:
                continue
            # 同行业匹配
            match = False
            for kw in sector_keywords:
                if kw.lower() in brief_asset.lower():
                    match = True
                    break
            if not match and report_type:
                match = brief_type == report_type

            if match:
                results.append({
                    "asset": brief_asset or key.split(":")[0],
                    "report_type": brief_type,
                    "rating": brief.get("rating", latest.get("rating", "")),
                    "target_price": brief.get("target_price", latest.get("target_price", "")),
                    "thesis": brief.get("thesis", latest.get("thesis", ""))[:200],
                    "date": latest.get("created_at", ""),
                })

        return results[:limit]

    @staticmethod
    def diff(new_scaffold: ArgumentScaffold,
             old_cache: dict) -> dict:
        """Diff new scaffold against cached version.

        Returns: {
          "changed_sections": [section_id, ...],
          "unchanged_sections": [section_id, ...],
          "is_new": bool,
          "old_fingerprint": str,
          "new_fingerprint": str,
        }
        """
        old_sections = {
            s["section_id"]: s
            for s in old_cache.get("scaffold", {}).get("sections", [])
        }

        changed = []
        unchanged = []
        for sec in new_scaffold.sections:
            old = old_sections.get(sec.section_id)
            if old:
                new_fp = _section_fingerprint(sec)
                old_fp = old.get("fingerprint", "")
                if new_fp == old_fp:
                    unchanged.append(sec.section_id)
                else:
                    changed.append(sec.section_id)
            else:
                changed.append(sec.section_id)

        return {
            "changed_sections": changed,
            "unchanged_sections": unchanged,
            "is_new": len(unchanged) == 0,
            "old_fingerprint": old_cache.get("fingerprint", ""),
            "new_fingerprint": _scaffold_fingerprint(new_scaffold),
        }

    @staticmethod
    def list_history(asset_code: str, report_type: str,
                     limit: int = 5) -> list[dict]:
        """List scaffold history for an asset."""
        cache = _get_cache()
        key = f"{asset_code}:{report_type}"
        entries = cache.get("reports", {}).get(key, [])
        return [
            {
                "fingerprint": e.get("fingerprint", ""),
                "created_at": e.get("created_at", ""),
                "brief_id": e.get("brief_id", ""),
                "core_thesis": e.get("brief", {}).get("core_thesis", {}).get("point", ""),
            }
            for e in entries[-limit:]
        ][::-1]

    @staticmethod
    def count() -> int:
        """Total cached reports."""
        cache = _get_cache()
        count = 0
        for key, entries in cache.get("reports", {}).items():
            count += len(entries)
        return count

    @staticmethod
    def clear(asset_code: str = "", report_type: str = ""):
        """Clear cache entries."""
        if not asset_code and not report_type:
            # Clear all
            _save_cache({"version": "V51.1", "reports": {}})
            logger.info("Cleared all report cache")
            return

        cache = _get_cache()
        if asset_code and report_type:
            key = f"{asset_code}:{report_type}"
            cache.get("reports", {}).pop(key, None)
        _save_cache(cache)
