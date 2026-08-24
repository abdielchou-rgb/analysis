"""预测闭环激活器 — 让 prediction_loop 从骨架变成工作循环。

接入流程：预测(写报告时) → 存入 predictions.json → 到期自动验证
  → 回测偏差 → 更新置信度 → 反馈到下一份报告。
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.prediction_loop")

PREDICTION_DB = Path(__file__).resolve().parent.parent / "data" / "predictions.json"


def _load() -> dict:
    if PREDICTION_DB.exists():
        try:
            return json.loads(PREDICTION_DB.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": "V2", "predictions": [], "backtest_results": []}


def _save(data: dict):
    PREDICTION_DB.parent.mkdir(parents=True, exist_ok=True)
    PREDICTION_DB.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class PredictionLoop:
    """Record -> verify -> confidence update cycle."""

    def __init__(self):
        self.data = _load()

    def record(self, code: str, statement: str, predictor: str = "analyst",
               target_value: float = None, due_date: str = None):
        """写报告时记录预测。"""
        pred = {
            "id": f"pred_{len(self.data['predictions'])+1}",
            "code": code, "statement": statement,
            "predictor": predictor,
            "target_value": target_value,
            "recorded_at": datetime.now().isoformat(),
            "due_date": due_date or (datetime.now() + timedelta(days=365)).isoformat(),
            "verified": False, "actual_value": None,
            "deviation_pct": None, "confidence_updated": False,
        }
        self.data["predictions"].append(pred)
        logger.info(f"[PREDICTION] 记录: {code} - {statement[:40]}...")
        _save(self.data)
        return pred["id"]

    def verify(self, pred_id: str, actual_value: float) -> dict:
        """新数据到达时验证预测。"""
        for p in self.data["predictions"]:
            if p["id"] == pred_id:
                p["verified"] = True
                p["actual_value"] = actual_value
                if p.get("target_value"):
                    p["deviation_pct"] = round(
                        (actual_value - p["target_value"]) / abs(p["target_value"]) * 100, 2
                    )
                    p["confidence_updated"] = True
                _save(self.data)
                logger.info(f"[VERIFY] {pred_id}: actual={actual_value}, dev={p.get('deviation_pct')}%")
                return p
        return {"error": f"预测 {pred_id} 不存在"}

    def backtest_summary(self) -> str:
        """回测总结。"""
        total = len(self.data["predictions"])
        verified = sum(1 for p in self.data["predictions"] if p["verified"])
        if verified == 0:
            return f"预测记录: {total}条, 已验证: 0条（尚无到期验证）"
        deviations = [p["deviation_pct"] for p in self.data["predictions"]
                      if p.get("deviation_pct") is not None]
        if not deviations:
            return f"预测记录: {total}条, 已验证: {verified}条（无量化偏差数据）"
        avg_dev = sum(abs(d) for d in deviations) / len(deviations)
        within_10 = sum(1 for d in deviations if abs(d) <= 10)
        hit_rate = within_10 / len(deviations) * 100
        lines = [
            f"=== 预测回测总结 ===",
            f"总预测: {total}条 | 已验证: {verified}条",
            f"平均绝对偏差: {avg_dev:.2f}% | ±10%命中率: {hit_rate:.0f}%",
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    pl = PredictionLoop()
    print(pl.backtest_summary())
