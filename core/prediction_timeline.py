"""C6: Updateable predictions with timeline.

track_record supports prediction update events (revised judgment,
added conviction). Calibration is computed on the latest point estimate.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("2hao.prediction_update")


class PredictionTimeline:
    """Manages prediction updates with full timeline."""

    def __init__(self, timeline_path: str = "core/data/forward_picks/prediction_timelines.json"):
        self.timeline_path = Path(timeline_path)
        self.timeline_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_timelines(self) -> dict:
        if not self.timeline_path.exists():
            return {}
        with open(self.timeline_path, encoding="utf-8") as f:
            return json.load(f)

    def _save_timelines(self, timelines: dict):
        with open(self.timeline_path, "w", encoding="utf-8") as f:
            json.dump(timelines, f, ensure_ascii=False, indent=2)

    def record_update(
        self,
        prediction_id: str,
        update_type: str = "revision",
        field_changed: str = "",
        old_value: Any = None,
        new_value: Any = None,
        reason: str = "",
        confidence_before: float = None,
        confidence_after: float = None,
    ) -> dict:
        """Record a prediction update event.

        Args:
            prediction_id: Unique prediction identifier
            update_type: "revision", "confidence_change", "direction_change", "addition"
            field_changed: Which field was changed
            old_value: Previous value
            new_value: New value
            reason: Why the change was made
            confidence_before: Confidence before update
            confidence_after: Confidence after update

        Returns:
            The recorded update event
        """
        timelines = self._load_timelines()

        if prediction_id not in timelines:
            timelines[prediction_id] = {
                "prediction_id": prediction_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updates": [],
                "current_state": {},
            }

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "update_type": update_type,
            "field_changed": field_changed,
            "old_value": str(old_value)[:500] if old_value is not None else None,
            "new_value": str(new_value)[:500] if new_value is not None else None,
            "reason": reason[:500],
            "confidence_before": confidence_before,
            "confidence_after": confidence_after,
        }

        timelines[prediction_id]["updates"].append(event)

        # Update current state
        if field_changed and new_value is not None:
            timelines[prediction_id]["current_state"][field_changed] = new_value
        if confidence_after is not None:
            timelines[prediction_id]["current_state"]["confidence"] = confidence_after

        self._save_timelines(timelines)
        logger.info("[PREDICTION-UPDATE] %s: %s changed %s (%s → %s)",
                     prediction_id, update_type, field_changed, old_value, new_value)
        return event

    def get_timeline(self, prediction_id: str) -> dict:
        """Get the full timeline for a prediction."""
        timelines = self._load_timelines()
        return timelines.get(prediction_id, {
            "prediction_id": prediction_id,
            "updates": [],
            "current_state": {},
        })

    def get_latest_confidence(self, prediction_id: str) -> Optional[float]:
        """Get the latest confidence for a prediction."""
        timeline = self.get_timeline(prediction_id)
        state = timeline.get("current_state", {})
        return state.get("confidence")

    def get_update_count(self, prediction_id: str) -> int:
        """Get the number of updates for a prediction."""
        timeline = self.get_timeline(prediction_id)
        return len(timeline.get("updates", []))

    def has_direction_change(self, prediction_id: str) -> bool:
        """Check if the prediction's direction was ever changed."""
        timeline = self.get_timeline(prediction_id)
        for update in timeline.get("updates", []):
            if update.get("field_changed") == "direction":
                return True
        return False

    def generate_timeline_report(self, output_dir: str = "output") -> dict:
        """Generate report on prediction update activity."""
        timelines = self._load_timelines()

        stats = {
            "total_predictions_with_updates": len(timelines),
            "total_update_events": sum(len(t.get("updates", [])) for t in timelines.values()),
            "direction_changes": sum(
                1 for t in timelines.values()
                if any(u.get("field_changed") == "direction" for u in t.get("updates", []))
            ),
            "confidence_changes": sum(
                1 for t in timelines.values()
                if any(u.get("update_type") == "confidence_change" for u in t.get("updates", []))
            ),
            "avg_updates_per_prediction": 0,
        }

        if stats["total_predictions_with_updates"] > 0:
            stats["avg_updates_per_prediction"] = round(
                stats["total_update_events"] / stats["total_predictions_with_updates"], 2
            )

        # Most updated predictions
        most_updated = sorted(
            timelines.items(),
            key=lambda x: len(x[1].get("updates", [])),
            reverse=True,
        )[:10]

        report = {
            **stats,
            "most_updated_predictions": [
                {
                    "prediction_id": pid,
                    "update_count": len(t.get("updates", [])),
                    "current_state": t.get("current_state", {}),
                }
                for pid, t in most_updated
            ],
        }

        # Save report
        out_path = Path(output_dir) / "timeline_report.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("[TIMELINE] Report saved: %s (updates=%d)",
                    out_path, stats["total_update_events"])
        return report
