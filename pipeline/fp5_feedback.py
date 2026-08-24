"""FP5 最小反馈闭环 — 报告交付后自动学习"""
from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger("2hao.fp5")


class FP5FeedbackLoop:
    """FP5 演化 — 从报告交付结果学习并更新规则。"""
    HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "fp5_history.json"

    def __init__(self):
        self.history = self._load_history()

    def _load_history(self) -> dict:
        if self.HISTORY_PATH.exists():
            try:
                return json.loads(self.HISTORY_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"reports": [], "failure_patterns": {}, "rule_updates": []}

    def _save_history(self):
        self.HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.HISTORY_PATH.write_text(
            json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8")

    def on_report_delivered(self, asset, report_type, gate_passed, gate_score, failures):
        entry = {
            "asset": asset, "report_type": report_type,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "gate_passed": gate_passed, "gate_score": gate_score,
            "failures": [{"name": f.get("name",""), "class": f.get("class",""),
                          "severity": f.get("severity","warning")} for f in failures],
        }
        self.history["reports"].append(entry)
        for f in failures:
            n = f.get("name", "")
            self.history["failure_patterns"][n] = self.history["failure_patterns"].get(n, 0) + 1
        self._save_history()

    def get_stats(self) -> str:
        n = len(self.history["reports"])
        passed = sum(1 for r in self.history["reports"] if r["gate_passed"])
        avg_score = sum(r["gate_score"] for r in self.history["reports"]) / max(n, 1) if n else 0
        return f"FP5: {n}份报告, {passed}通过, 均分{avg_score:.3f}"

if __name__ == "__main__":
    print(FP5FeedbackLoop().get_stats())
