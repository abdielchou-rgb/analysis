"""D5: HITL durable — approval requests survive process crashes.

Records approval requests in ledger. On crash recovery, finds stale
approval requests and resumes from export node when approved.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.hitl_durable")


class HITLApprovalManager:
    """Durable human-in-the-loop approval manager."""

    def __init__(self, review_dir: str = "data/reviews", ledger_dir: str = "output/ledgers"):
        self.review_dir = Path(review_dir)
        self.review_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_dir = Path(ledger_dir)
        self.ledger_dir.mkdir(parents=True, exist_ok=True)

    def request_approval(
        self,
        job_id: str,
        asset: str,
        report_type: str,
        context_snapshot: dict = None,
        reason: str = "",
    ) -> str:
        """Record an approval request. Returns review file path."""
        review_data = {
            "job_id": job_id,
            "asset": asset,
            "report_type": report_type,
            "decision": "pending",
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "context_snapshot": context_snapshot or {},
            "reviewer": "",
            "reviewed_at": "",
            "notes": "",
        }
        review_path = self.review_dir / f"{job_id}.json"
        review_path.write_text(json.dumps(review_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Also record in ledger for crash recovery
        ledger_file = self.ledger_dir / "hitl_approvals.jsonl"
        with open(ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "job_id": job_id,
                "asset": asset,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "review_path": str(review_path),
            }, ensure_ascii=False) + "\n")

        logger.info("[HITL] Approval requested: %s (asset=%s)", job_id, asset)
        return str(review_path)

    def check_approval(self, job_id: str) -> dict:
        """Check if a job has been approved."""
        review_path = self.review_dir / f"{job_id}.json"
        if not review_path.exists():
            return {"status": "not_found", "decision": None}
        try:
            data = json.loads(review_path.read_text(encoding="utf-8"))
            return {
                "status": "found",
                "decision": data.get("decision", "pending"),
                "reviewer": data.get("reviewer", ""),
                "reviewed_at": data.get("reviewed_at", ""),
                "notes": data.get("notes", ""),
            }
        except Exception as e:
            return {"status": "error", "decision": None, "error": str(e)}

    def approve(
        self,
        job_id: str,
        reviewer: str = "human",
        notes: str = "",
    ) -> bool:
        """Approve a job."""
        review_path = self.review_dir / f"{job_id}.json"
        if not review_path.exists():
            logger.warning("[HITL] Review file not found: %s", job_id)
            return False

        data = json.loads(review_path.read_text(encoding="utf-8"))
        data["decision"] = "approved"
        data["reviewer"] = reviewer
        data["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        data["notes"] = notes
        review_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info("[HITL] Approved: %s by %s", job_id, reviewer)
        return True

    def reject(
        self,
        job_id: str,
        reviewer: str = "human",
        reason: str = "",
    ) -> bool:
        """Reject a job."""
        review_path = self.review_dir / f"{job_id}.json"
        if not review_path.exists():
            return False

        data = json.loads(review_path.read_text(encoding="utf-8"))
        data["decision"] = "rejected"
        data["reviewer"] = reviewer
        data["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        data["notes"] = reason
        review_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info("[HITL] Rejected: %s by %s — %s", job_id, reviewer, reason[:100])
        return True

    def find_stale_approvals(self) -> list[dict]:
        """Find approval requests that were pending when process crashed."""
        ledger_file = self.ledger_dir / "hitl_approvals.jsonl"
        if not ledger_file.exists():
            return []

        stale = []
        for line in ledger_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("status") == "pending":
                    # Check current status
                    current = self.check_approval(entry["job_id"])
                    if current["decision"] == "pending":
                        stale.append(entry)
            except json.JSONDecodeError:
                pass
        return stale

    def resume_after_approval(self, job_id: str, export_func, context: dict) -> dict:
        """Resume pipeline from export node after approval.

        Call this after finding a stale approval that is now approved.
        """
        approval = self.check_approval(job_id)
        if approval["decision"] != "approved":
            logger.info("[HITL] Cannot resume %s: decision=%s", job_id, approval["decision"])
            return {"resumed": False, "decision": approval["decision"]}

        logger.info("[HITL] Resuming %s after approval", job_id)
        try:
            result = export_func(context)
            return {"resumed": True, "result": result}
        except Exception as e:
            logger.error("[HITL] Resume failed for %s: %s", job_id, str(e))
            return {"resumed": False, "error": str(e)}
