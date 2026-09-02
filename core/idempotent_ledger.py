"""D4: Idempotent ledger — side effects recorded as pending before execution.

Prevents duplicate/lost side effects on crash recovery.
Pattern: record pending → execute → mark done. Crash → recover from ledger.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger("2hao.ledger")


class LedgerEntryStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class LedgerEntry:
    """A single ledger entry for a side effect."""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    entry_type: str = ""  # export_docx, write_record, send_notification, etc.
    asset: str = ""
    params: dict = field(default_factory=dict)
    status: str = LedgerEntryStatus.PENDING.value
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    result: Any = None
    error: str = ""
    retries: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class IdempotentLedger:
    """Persistent ledger for side effect idempotency."""

    def __init__(self, ledger_dir: str = "output/ledgers"):
        self.ledger_dir = Path(ledger_dir)
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self._ledger_file = self.ledger_dir / "side_effects.jsonl"

    def _load_entries(self) -> list[dict]:
        if not self._ledger_file.exists():
            return []
        entries = []
        for line in self._ledger_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries

    def _append_entry(self, entry: LedgerEntry):
        with open(self._ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    def _update_entry(self, entry_id: str, updates: dict):
        entries = self._load_entries()
        with open(self._ledger_file, "w", encoding="utf-8") as f:
            for e in entries:
                if e["id"] == entry_id:
                    e.update(updates)
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def record_pending(self, entry_type: str, asset: str, params: dict = None) -> str:
        """Record a side effect as pending. Returns entry ID."""
        entry = LedgerEntry(
            entry_type=entry_type,
            asset=asset,
            params=params or {},
            status=LedgerEntryStatus.PENDING.value,
        )
        self._append_entry(entry)
        logger.info("[LEDGER] Recorded pending: %s/%s (id=%s)", asset, entry_type, entry.id)
        return entry.id

    def mark_running(self, entry_id: str):
        self._update_entry(entry_id, {
            "status": LedgerEntryStatus.RUNNING.value,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

    def mark_done(self, entry_id: str, result: Any = None):
        self._update_entry(entry_id, {
            "status": LedgerEntryStatus.DONE.value,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": str(result)[:500] if result else "",
        })
        logger.info("[LEDGER] Marked done: %s", entry_id)

    def mark_failed(self, entry_id: str, error: str):
        self._update_entry(entry_id, {
            "status": LedgerEntryStatus.FAILED.value,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": error[:500],
        })
        logger.warning("[LEDGER] Marked failed: %s — %s", entry_id, error[:100])

    def get_pending(self, entry_type: str = None, asset: str = None) -> list[dict]:
        """Get all pending entries, optionally filtered by type/asset."""
        entries = self._load_entries()
        return [
            e for e in entries
            if e["status"] in (LedgerEntryStatus.PENDING.value, LedgerEntryStatus.RUNNING.value)
            and (entry_type is None or e["entry_type"] == entry_type)
            and (asset is None or e["asset"] == asset)
        ]

    def is_duplicate(self, entry_type: str, asset: str, params: dict = None) -> bool:
        """Check if an identical entry already exists (pending or done)."""
        entries = self._load_entries()
        for e in entries:
            if (e["entry_type"] == entry_type
                and e["asset"] == asset
                and e["status"] in (LedgerEntryStatus.DONE.value, LedgerEntryStatus.PENDING.value)):
                # Check params match
                if params and e.get("params") == params:
                    return True
                elif not params:
                    return True
        return False

    def execute_with_idempotency(
        self,
        entry_type: str,
        asset: str,
        func: Callable,
        params: dict = None,
        *args, **kwargs,
    ) -> Any:
        """Execute a side effect with idempotency guarantees.

        1. Check if duplicate exists → return cached result
        2. Record pending
        3. Execute
        4. Mark done/failed
        """
        # Check for duplicate
        if self.is_duplicate(entry_type, asset, params):
            logger.info("[LEDGER] Duplicate detected: %s/%s, skipping", asset, entry_type)
            existing = self.get_pending(entry_type, asset)
            if existing and existing[0].get("result"):
                return existing[0]["result"]
            return None

        # Record pending
        entry_id = self.record_pending(entry_type, asset, params)

        try:
            self.mark_running(entry_id)
            result = func(*args, **kwargs)
            self.mark_done(entry_id, result)
            return result
        except Exception as e:
            self.mark_failed(entry_id, str(e))
            raise

    def recover_incomplete(self) -> list[dict]:
        """Get all entries that were running when process crashed (stale)."""
        entries = self._load_entries()
        stale = []
        for e in entries:
            if e["status"] == LedgerEntryStatus.RUNNING.value:
                stale.append(e)
        return stale

    def summary(self) -> dict:
        """Get ledger summary statistics."""
        entries = self._load_entries()
        counts = {}
        for e in entries:
            s = e.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return {
            "total": len(entries),
            "by_status": counts,
            "ledger_file": str(self._ledger_file),
        }
