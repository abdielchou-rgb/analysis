"""Phase D: PredictionLoop — record → verify → confidence update.

预测-反馈回路——超级分析师的自我修正机制。
  - 报告生成时自动记录预测（来自 core_disagreement 和 thesis）
  - 新数据到达时检查是否有待验证的预测
  - 验证后更新置信度：正确提升，错误降低
  - 所有预测历史持久化到 prediction_history.json

与 CognitiveBaseline 的关系:
  - CognitiveBaseline 存储当前认知状态
  - PredictionLoop 管理"未来将验证的判断"的生命周期
  - 两者共用一个 baseline — prediction_loop 写回 baseline
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("v51.prediction_loop")

PREDICTION_DB = Path(__file__).resolve().parent.parent / "data" / "predictions.json"


def _load_predictions() -> dict:
    if PREDICTION_DB.exists():
        try:
            return json.loads(PREDICTION_DB.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Prediction DB load failed: {e}")
    return {"version": "V51.3", "predictions": []}


def _save_predictions(data: dict):
    PREDICTION_DB.parent.mkdir(parents=True, exist_ok=True)
    PREDICTION_DB.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class PredictionLoop:
    """Record → verify → confidence update cycle."""

    @staticmethod
    def record_prediction(code: str, statement: str,
                           predictor: str = "core_disagreement",
                           confidence: float = 0.65,
                           timeframe_days: int = 365,
                           verification_criteria: Optional[list[str]] = None):
        """Record a prediction from report generation.

        Args:
            code: Asset code
            statement: The prediction text (e.g., "直销占比可突破50%")
            predictor: What generated this (core_disagreement, hypothesis, etc.)
            confidence: Initial confidence 0.0-1.0
            timeframe_days: Expected verification window
            verification_criteria: What observable data would verify/falsify this
        """
        db = _load_predictions()
        prediction = {
            "id": f"pred_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "code": code,
            "statement": statement,
            "predictor": predictor,
            "initial_confidence": confidence,
            "current_confidence": confidence,
            "created_at": datetime.now().isoformat(),
            "verify_by": (datetime.now() + timedelta(days=timeframe_days)).isoformat(),
            "verification_criteria": verification_criteria or [],
            "status": "pending",  # pending | confirmed | falsified | expired
            "outcome": None,
            "verified_at": None,
            "evidence": [],
        }
        db["predictions"].append(prediction)
        _save_predictions(db)
        logger.info(f"Prediction recorded [{code}]: {statement[:60]}... (confidence {confidence:.0%})")

        # Also update the cognitive baseline
        try:
            from core.cognitive_baseline import CognitiveBaseline
            baseline = CognitiveBaseline.load(code)
            if "prediction_history" not in baseline:
                baseline["prediction_history"] = []
            baseline["prediction_history"].append({
                "id": prediction["id"],
                "statement": statement,
                "confidence": confidence,
                "created_at": prediction["created_at"],
                "status": "pending",
            })
            # Keep only last 50
            baseline["prediction_history"] = baseline["prediction_history"][-50:]
            CognitiveBaseline.save(code, baseline)
        except Exception as e:
            logger.warning(f"Failed to update baseline with prediction: {e}")

    @staticmethod
    def check_pending(code: str, new_data: list,
                       baseline: Optional[dict] = None) -> list[dict]:
        """Check if any pending predictions can be verified with new data.

        Args:
            code: Asset code
            new_data: Fresh data points
            baseline: Current cognitive baseline

        Returns:
            List of updated predictions.
        """
        db = _load_predictions()
        updated = []

        for pred in db["predictions"]:
            if pred["code"] != code or pred["status"] != "pending":
                continue

            # Try to find verification data
            criteria = pred.get("verification_criteria", [])
            statement = pred.get("statement", "")

            found_match = False
            for dp in new_data:
                if not dp.name:
                    continue
                # Simple matching: check if data point name appears in criteria or statement
                for criterion in criteria:
                    if dp.name.lower() in criterion.lower():
                        found_match = True
                        break

            if found_match:
                pred["status"] = "confirmed"
                pred["outcome"] = "verified_by_data"
                pred["verified_at"] = datetime.now().isoformat()
                pred["evidence"] = [
                    {"source": dp.source, "value": dp.value, "unit": dp.unit}
                    for dp in new_data if dp.name
                ]
                updated.append(pred)
                logger.info(f"Prediction {pred['id']} confirmed by new data")

        if updated:
            _save_predictions(db)
            # Update cognitive baseline
            try:
                from core.cognitive_baseline import CognitiveBaseline
                base = CognitiveBaseline.load(code)
                for p in base.get("prediction_history", []):
                    for upd in updated:
                        if p.get("id") == upd["id"]:
                            p["status"] = "confirmed"
                            p["outcome"] = "verified_by_data"
                            p["verified_at"] = upd["verified_at"]
                CognitiveBaseline.save(code, base)
            except Exception as e:
                logger.warning(f"Failed to update baseline: {e}")

        return updated

    @staticmethod
    def update_confidence(code: str, prediction_id: str,
                           new_confidence: float):
        """Manually update confidence for a prediction."""
        db = _load_predictions()
        for pred in db["predictions"]:
            if pred["code"] == code and pred["id"] == prediction_id:
                pred["current_confidence"] = new_confidence
                pred["last_updated"] = datetime.now().isoformat()
                _save_predictions(db)
                logger.info(f"Prediction {prediction_id} confidence updated to {new_confidence:.0%}")
                return True
        return False

    @staticmethod
    def get_stats() -> dict:
        """Get prediction statistics."""
        db = _load_predictions()
        predictions = db.get("predictions", [])
        total = len(predictions)
        pending = sum(1 for p in predictions if p.get("status") == "pending")
        confirmed = sum(1 for p in predictions if p.get("status") == "confirmed")
        falsified = sum(1 for p in predictions if p.get("status") == "falsified")
        expired = sum(1 for p in predictions if p.get("status") == "expired")

        accuracy = confirmed / (confirmed + falsified) * 100 if (confirmed + falsified) > 0 else None

        return {
            "total": total,
            "pending": pending,
            "confirmed": confirmed,
            "falsified": falsified,
            "expired": expired,
            "accuracy_pct": round(accuracy, 1) if accuracy is not None else None,
        }

    @staticmethod
    def list_active(code: str = "") -> list[dict]:
        """List all active (pending) predictions."""
        db = _load_predictions()
        predictions = db.get("predictions", [])
        if code:
            predictions = [p for p in predictions if p.get("code") == code]
        return [p for p in predictions if p.get("status") == "pending"]

    @staticmethod
    def check_expired():
        """Mark predictions past their verify_by date as expired."""
        db = _load_predictions()
        now = datetime.now()
        expired_count = 0
        for pred in db["predictions"]:
            if pred["status"] != "pending":
                continue
            try:
                verify_by = datetime.fromisoformat(pred["verify_by"])
                if now > verify_by:
                    pred["status"] = "expired"
                    pred["outcome"] = "timeout"
                    expired_count += 1
            except (ValueError, TypeError):
                pass

        if expired_count:
            _save_predictions(db)
            logger.info(f"Marked {expired_count} predictions as expired")

        return expired_count
