"""Phase A: CognitiveBaseline — persistent cognitive state per covered asset.

每个覆盖标的的持久化认知状态：
  - 关键变量 (key_variables) + 当前值 + 变化方向
  - 活跃假说 (active_hypotheses) + 置信度 + 待验证观察
  - 预测历史 (prediction_history) — 记录→验证→修正
  - 数据新鲜度 (data_freshness) — 每个数据维度的最后更新时间
  - 已知模式 (known_patterns) — 系统已识别的跨时间模式

集成点: workflow.py 中 write/hypothesis 后自动调用
  from core.cognitive_baseline import CognitiveBaseline
  baseline = CognitiveBaseline()
  baseline.initialize_from_report(scaffold, kp)
  baseline.update(asset_code, new_data)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from core.models import (
    ArgumentScaffold,
    DataPoint,
    KnowledgePackage,
    WritingBrief,
)

logger = logging.getLogger("v51.cognitive_baseline")

BASELINE_DIR = Path(__file__).resolve().parent.parent / "data" / "cognitive_baseline"


def _ensure_dir():
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)


def _baseline_path(code: str) -> Path:
    return BASELINE_DIR / f"{code}.json"


# ── Data model ───────────────────────────────────────────────

DEFAULT_BASELINE = {
    "version": "V51.3",
    "code": "",
    "name": "",
    "last_updated": "",
    "key_variables": {},
    "active_hypotheses": [],
    "prediction_history": [],
    "data_freshness": {},
    "known_patterns": [],
    "report_history": [],
    "cognitive_summary": "",
}


# ── Baseline CRUD ────────────────────────────────────────────


class CognitiveBaseline:
    """Persistent cognitive state for each covered asset."""

    @staticmethod
    def load(code: str) -> dict:
        """Load baseline for an asset code."""
        path = _baseline_path(code)
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Baseline load failed for {code}: {e}")
        return {**DEFAULT_BASELINE, "code": code, "last_updated": datetime.now().isoformat()}

    @staticmethod
    def save(code: str, baseline: dict):
        """Save baseline for an asset code."""
        _ensure_dir()
        baseline["last_updated"] = datetime.now().isoformat()
        path = _baseline_path(code)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(baseline, f, ensure_ascii=False, indent=2)
        logger.info(
            f"Baseline saved for {code} ({len(baseline.get('key_variables', {}))} vars, "
            f"{len(baseline.get('active_hypotheses', []))} hypotheses)"
        )

    @staticmethod
    def exists(code: str) -> bool:
        return _baseline_path(code).exists()

    @staticmethod
    def delete(code: str):
        path = _baseline_path(code)
        if path.exists():
            path.unlink()
            logger.info(f"Baseline deleted for {code}")

    # ── Initialization from report ──

    @staticmethod
    def initialize_from_report(scaffold: ArgumentScaffold, kp: KnowledgePackage) -> dict:
        """Create/update baseline from a generated report's scaffold + KP.

        Called automatically after write().
        """
        brief = kp.brief or WritingBrief()
        code = brief.asset_code or brief.asset
        if not code:
            logger.warning("No asset code in brief, skipping baseline")
            return {}

        baseline = CognitiveBaseline.load(code)
        baseline["code"] = code
        baseline["name"] = brief.asset

        # Extract key variables from scaffold
        for section in scaffold.sections:
            if section.section_id == "core_disagreement":
                # Extract from core_disagreement field
                cd = scaffold.core_disagreement or {}
                kv = cd.get("key_variable", "") or brief.key_variable or ""
                if kv:
                    baseline["key_variables"][kv] = {
                        "value": "",
                        "direction": "stable",
                        "last_updated": datetime.now().isoformat(),
                        "source": "report_generation",
                    }

            # Add evidence-based variables
            for eid in section.evidence_ids:
                dp = next((d for d in (kp.data_points or []) if d.name == eid), None)
                if dp and dp.name:
                    baseline["key_variables"][dp.name] = {
                        "value": dp.value,
                        "unit": dp.unit,
                        "source": dp.source or "unknown",
                        "last_updated": datetime.now().isoformat(),
                        "direction": "stable",
                    }

        # Extract active hypotheses from core_disagreement
        our_view = brief.our_view or scaffold.core_disagreement.get("our_view", "")
        market_view = brief.market_consensus or scaffold.core_disagreement.get("market", "")
        if our_view:
            hypothesis = {
                "statement": our_view,
                "market_consensus": market_view,
                "confidence": 0.65,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "pending_observation": [],
                "verified": False,
                "falsified": False,
            }
            baseline["active_hypotheses"].append(hypothesis)
            # Keep only last 10
            baseline["active_hypotheses"] = baseline["active_hypotheses"][-10:]

        # Record this report
        baseline["report_history"].append(
            {
                "brief_id": scaffold.brief_id or brief.brief_id,
                "report_type": brief.report_type.value if brief.report_type else "unknown",
                "style": brief.style_profile,
                "created_at": datetime.now().isoformat(),
            }
        )
        baseline["report_history"] = baseline["report_history"][-20:]

        CognitiveBaseline.save(code, baseline)
        return baseline

    # ── Update with new data ──

    @staticmethod
    def update(code: str, new_data: list[DataPoint]) -> dict:
        """Update baseline with fresh data points.

        Returns dict of changes: {"changed_vars": [...], "new_vars": [...]}
        """
        baseline = CognitiveBaseline.load(code)
        changes = {"changed_vars": [], "new_vars": [], "no_change": []}

        for dp in new_data:
            if not dp.name:
                continue
            existing = baseline["key_variables"].get(dp.name)
            if existing:
                old_val = existing.get("value")
                if old_val != dp.value:
                    # Determine direction
                    try:
                        if isinstance(dp.value, (int, float)) and isinstance(old_val, (int, float)):
                            direction = "up" if dp.value > old_val else "down"
                        else:
                            direction = "changed"
                    except (TypeError, ValueError):
                        direction = "changed"
                    changes["changed_vars"].append(
                        {
                            "name": dp.name,
                            "old": old_val,
                            "new": dp.value,
                            "direction": direction,
                        }
                    )
                    existing["direction"] = direction
                else:
                    changes["no_change"].append(dp.name)
                existing["value"] = dp.value
                existing["unit"] = dp.unit or existing.get("unit", "")
                existing["source"] = dp.source or existing.get("source", "")
                existing["last_updated"] = datetime.now().isoformat()
            else:
                changes["new_vars"].append(dp.name)
                baseline["key_variables"][dp.name] = {
                    "value": dp.value,
                    "unit": dp.unit or "",
                    "source": dp.source or "unknown",
                    "last_updated": datetime.now().isoformat(),
                    "direction": "new",
                }

            # Update data freshness
            baseline.setdefault("data_freshness", {})[dp.name] = datetime.now().isoformat()

        CognitiveBaseline.save(code, baseline)
        return changes

    # ── Query ──

    @staticmethod
    def get_summary(code: str) -> dict:
        """Get a concise summary of the cognitive state."""
        baseline = CognitiveBaseline.load(code)
        return {
            "code": baseline.get("code", code),
            "name": baseline.get("name", ""),
            "key_variables_count": len(baseline.get("key_variables", {})),
            "active_hypotheses": [
                {"statement": h.get("statement", ""), "confidence": h.get("confidence", 0)}
                for h in baseline.get("active_hypotheses", [])
            ],
            "prediction_count": len(baseline.get("prediction_history", [])),
            "last_report": baseline.get("report_history", [{}])[-1].get("created_at", "")
            if baseline.get("report_history")
            else "",
            "data_freshness": baseline.get("data_freshness", {}),
        }

    @staticmethod
    def list_all() -> list[str]:
        """List all codes with baselines."""
        _ensure_dir()
        return sorted([f.stem for f in BASELINE_DIR.glob("*.json")])

    @staticmethod
    def count() -> int:
        return len(CognitiveBaseline.list_all())

    @staticmethod
    def get_assets_needing_update(hours: int = 24) -> list[str]:
        """Return codes where data_freshness is older than threshold."""
        from datetime import timedelta

        threshold = datetime.now() - timedelta(hours=hours)
        stale = []
        for code in CognitiveBaseline.list_all():
            baseline = CognitiveBaseline.load(code)
            freshness = baseline.get("data_freshness", {})
            all_stale = True
            for var_name, ts_str in freshness.items():
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts > threshold:
                        all_stale = False
                        break
                except (ValueError, TypeError):
                    pass
            if all_stale and freshness:
                stale.append(code)
        return stale
