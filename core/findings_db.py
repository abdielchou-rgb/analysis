"""
findings_db.py - Audit findings database with closed-loop lifecycle.
Every finding: discovered -> registered -> triaged -> fixed -> verified -> closed.
"""
import os, json, sqlite3, logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger("2hao.findings_db")

FINDINGS_DB_PATH = Path(__file__).resolve().parent.parent / "output" / "findings.db"


class FindingsDB:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(FINDINGS_DB_PATH)
        self._conn = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        c = self._get_conn()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS audit_findings (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                severity TEXT NOT NULL CHECK(severity IN ('P0','P1','P2')),
                file TEXT NOT NULL,
                line INTEGER,
                check_name TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open','fixed','verified','closed','wontfix')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                fixed_at TEXT,
                verified_at TEXT,
                fix_notes TEXT,
                verify_script TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT NOT NULL,
                run_at TEXT NOT NULL,
                files_scanned INTEGER,
                total_findings INTEGER,
                p0_count INTEGER,
                p1_count INTEGER,
                p2_count INTEGER,
                summary TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_findings_status ON audit_findings(status);
            CREATE INDEX IF NOT EXISTS idx_findings_severity ON audit_findings(severity);
        """)
        c.commit()

    def register_finding(self, finding: Dict) -> str:
        """Register a new finding or update existing one if same check+file+line"""
        c = self._get_conn()
        # Generate ID
        import hashlib
        raw = f"{finding['check_name']}:{finding['file']}:{finding.get('line',0)}"
        finding_id = "F-" + hashlib.md5(raw.encode()).hexdigest()[:8]

        now = datetime.now().isoformat()

        existing = c.execute(
            "SELECT id, status FROM audit_findings WHERE id=?", (finding_id,)
        ).fetchone()

        if existing:
            if existing["status"] == "closed" or existing["status"] == "wontfix":
                return finding_id  # Don't reopen closed findings
            # Update existing open finding
            c.execute("""
                UPDATE audit_findings SET
                    source=?, severity=?, description=?, updated_at=?
                WHERE id=?
            """, (finding.get("source","auto"), finding.get("severity","P1"),
                  finding["description"], now, finding_id))
        else:
            c.execute("""
                INSERT INTO audit_findings
                    (id, source, severity, file, line, check_name,
                     description, status, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?, 'open', ?, ?)
            """, (finding_id, finding.get("source","auto"),
                  finding.get("severity","P1"),
                  finding["file"], finding.get("line",0),
                  finding["check_name"], finding["description"],
                  now, now))

        c.commit()
        return finding_id

    def register_audit_run(self, session_name: str, report: Dict):
        """Record an audit session"""
        c = self._get_conn()
        c.execute("""
            INSERT INTO audit_sessions
                (session_name, run_at, files_scanned, total_findings,
                 p0_count, p1_count, p2_count, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_name, datetime.now().isoformat(),
            report.get("files_scanned", 0),
            report.get("total_findings", 0),
            report["summary"].get("P0_count", 0),
            report["summary"].get("P1_count", 0),
            report["summary"].get("P2_count", 0),
            json.dumps(report.get("by_severity", {}), ensure_ascii=False)
        ))
        c.commit()

    def mark_fixed(self, finding_id: str, notes: str = ""):
        c = self._get_conn()
        c.execute("""
            UPDATE audit_findings SET
                status='fixed', fixed_at=?, updated_at=?, fix_notes=?
            WHERE id=?
        """, (datetime.now().isoformat(), datetime.now().isoformat(),
              notes[:200], finding_id))
        c.commit()

    def mark_verified(self, finding_id: str):
        c = self._get_conn()
        c.execute("""
            UPDATE audit_findings SET
                status='verified', verified_at=?, updated_at=?
            WHERE id=?
        """, (datetime.now().isoformat(), datetime.now().isoformat(),
              finding_id))
        c.commit()

    def mark_wontfix(self, finding_id: str, reason: str = ""):
        c = self._get_conn()
        c.execute("""
            UPDATE audit_findings SET
                status='wontfix', updated_at=?, fix_notes=?
            WHERE id=?
        """, (datetime.now().isoformat(), reason[:200], finding_id))
        c.commit()

    def get_open_findings(self, severity: Optional[str] = None) -> List[Dict]:
        c = self._get_conn()
        query = "SELECT * FROM audit_findings WHERE status='open'"
        params = []
        if severity:
            query += " AND severity=?"
            params.append(severity)
        query += " ORDER BY CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END, created_at DESC"
        return [dict(r) for r in c.execute(query, params).fetchall()]

    def get_all_findings(self, status: Optional[str] = None) -> List[Dict]:
        c = self._get_conn()
        if status:
            rows = c.execute("SELECT * FROM audit_findings WHERE status=? ORDER BY created_at DESC", (status,))
        else:
            rows = c.execute("SELECT * FROM audit_findings ORDER BY created_at DESC")
        return [dict(r) for r in rows.fetchall()]

    def get_stats(self) -> Dict:
        c = self._get_conn()
        result = {"total": 0, "open": 0, "fixed": 0, "verified": 0, "closed": 0,
                  "p0_open": 0, "p1_open": 0, "p2_open": 0, "sessions": 0}
        total = c.execute("SELECT COUNT(*) as cnt FROM audit_findings").fetchone()
        result["total"] = total["cnt"] if total else 0
        for status in ["open", "fixed", "verified", "closed"]:
            row = c.execute("SELECT COUNT(*) as cnt FROM audit_findings WHERE status=?", (status,)).fetchone()
            result[status] = row["cnt"] if row else 0
        for sev in ["P0", "P1", "P2"]:
            row = c.execute("SELECT COUNT(*) as cnt FROM audit_findings WHERE status='open' AND severity=?",
                          (sev,)).fetchone()
            result[f"{sev.lower()}_open"] = row["cnt"] if row else 0
        sess = c.execute("SELECT COUNT(*) as cnt FROM audit_sessions").fetchone()
        result["sessions"] = sess["cnt"] if sess else 0
        return result

    def format_status(self) -> str:
        s = self.get_stats()
        lines = []
        lines.append("=" * 50)
        lines.append("Findings DB Status")
        lines.append("=" * 50)
        lines.append(f"Total findings: {s['total']}")
        lines.append(f"  Open: {s['open']} (P0={s['p0_open']} P1={s['p1_open']} P2={s['p2_open']})")
        lines.append(f"  Fixed: {s['fixed']}")
        lines.append(f"  Verified: {s['verified']}")
        lines.append(f"  Closed: {s['closed']}")
        lines.append(f"Audit sessions: {s['sessions']}")
        if s["p0_open"] > 0:
            lines.append("\nOpen P0 findings:")
            for f in self.get_open_findings("P0"):
                lines.append(f"  [{f['id']}] {f['file']}:{f['line']} - {f['description']}")
        return "\n".join(lines)


def run_audit_and_register(db: FindingsDB, project_root: str, session_name: str) -> Dict:
    """Run audit engine scan and register all findings"""
    from core.audit_engine import scan_project
    report = scan_project(project_root)
    for f in report["findings"]:
        db.register_finding({
            "check_name": f["check"],
            "file": f["file"],
            "line": f["line"],
            "severity": f["severity"],
            "description": f"{f['description']}: {f['message']}",
            "source": session_name,
        })
    db.register_audit_run(session_name, report)
    return report


if __name__ == "__main__":
    db = FindingsDB()
    print(db.format_status())
    # Auto-register current state
    report = run_audit_and_register(db, str(Path(__file__).resolve().parent.parent), "v70-audit-engine-initial")
    print(f"\nRegistered {report['total_findings']} findings from initial audit")
