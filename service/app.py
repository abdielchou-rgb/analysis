"""
2号分析师 Research Service（Phase D，2026-09-06）。

FastAPI 服务面：把 scheduler 变成多用户可调度的研究服务。
架构约束（升级方案）：单 worker 子进程 + SQLite 任务表——并发 1-3 的系统
不上 Kafka/Celery/微服务，分布式化只会得到分布式的平庸。

端点：
    POST /api/v1/research              创建研究任务（后台跑完整管线）
    GET  /api/v1/research/{id}/status   任务状态
    GET  /api/v1/research/{id}/report   最终报告 (markdown)
    GET  /api/v1/research/{id}/evidence 证据账本（若产出）
    GET  /api/v1/health                 健康检查

启动：
    uvicorn service.app:app --port 8420

工件落盘位置（与单机 scheduler 一致，Workspace 只差一个渲染层）：
    output/{asset}/  报告 / lineage / fingerprint / gate report
"""

from __future__ import annotations

import logging
import sqlite3
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("2hao.service")

DB_PATH = _ANALYST_ROOT / "service" / "research_tasks.db"
OUTPUT_DIR = _ANALYST_ROOT / "output"

app = FastAPI(title="2hao Analyst Research Service", version="0.1.0")

# ── 任务存储（SQLite，单文件，零运维） ──────────────────────────────────


def _db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                asset TEXT NOT NULL,
                report_type TEXT DEFAULT 'listed_company',
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                started_at TEXT,
                finished_at TEXT,
                pid INTEGER,
                log_tail TEXT
            )
            """
        )


_init_db()

# ── 后台执行（单 worker 串行队列——LLM provider 并发就是 1-3） ──────────

_QUEUE: list[str] = []
_LOCK = threading.Lock()


def _run_task(task_id: str, asset: str, report_type: str):
    """子进程跑 scheduler，落盘状态 + 日志尾部。"""
    started = datetime.now(timezone.utc).isoformat()[:19]
    with _db() as conn:
        conn.execute("UPDATE tasks SET status='running', started_at=? WHERE id=?", (started, task_id))
    try:
        env = {**dict(__import__("os").environ), "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen(
            [sys.executable, str(_ANALYST_ROOT / "main.py"), asset, "--type", report_type],
            cwd=_ANALYST_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        with _db() as conn:
            conn.execute("UPDATE tasks SET pid=? WHERE id=?", (proc.pid, task_id))
        out, _ = proc.communicate(timeout=3600)
        status = "done" if proc.returncode == 0 else "failed"
        log_tail = (out or "")[-2000:]
    except subprocess.TimeoutExpired:
        status, log_tail = "timeout", "subprocess timeout (3600s)"
    except Exception as e:
        status, log_tail = "failed", f"{type(e).__name__}: {e}"
    finished = datetime.now(timezone.utc).isoformat()[:19]
    with _db() as conn:
        conn.execute(
            "UPDATE tasks SET status=?, finished_at=?, log_tail=? WHERE id=?",
            (status, finished, log_tail, task_id),
        )


def _worker_loop():
    """串行 worker：从队列取任务逐个跑。"""
    while True:
        task = None
        with _LOCK:
            if _QUEUE:
                task = _QUEUE.pop(0)
        if not task:
            threading.Event().wait(1.0)
            continue
        try:
            with _db() as conn:
                row = conn.execute("SELECT * FROM tasks WHERE id=?", (task,)).fetchone()
            if row:
                _run_task(task, row["asset"], row["report_type"])
        except Exception:
            logger.exception("worker error on %s", task)


threading.Thread(target=_worker_loop, daemon=True).start()


# ── API 模型 ────────────────────────────────────────────────────────────


class ResearchCreate(BaseModel):
    asset: str = Field(..., description="资产，如 '600519 贵州茅台'")
    report_type: str = Field(
        "listed_company", description="listed_company/industry_deep/unlisted_company/earnings_notes"
    )


# ── 端点 ─────────────────────────────────────────────────────────────────


@app.get("/api/v1/health")
def health():
    with _db() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM tasks").fetchone()["c"]
    return {"status": "ok", "db": str(DB_PATH), "tasks_total": n, "queue_depth": len(_QUEUE)}


@app.post("/api/v1/research")
def create_research(req: ResearchCreate):
    task_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat()[:19]
    with _db() as conn:
        conn.execute(
            "INSERT INTO tasks (id, asset, report_type, status, created_at) VALUES (?,?,?,?,?)",
            (task_id, req.asset, req.report_type, "queued", created),
        )
    with _LOCK:
        _QUEUE.append(task_id)
    return {"research_id": task_id, "status": "queued", "created_at": created}


@app.get("/api/v1/research/{task_id}/status")
def task_status(task_id: str):
    with _db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"task {task_id} not found")
    return {
        "research_id": row["id"],
        "asset": row["asset"],
        "report_type": row["report_type"],
        "status": row["status"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "log_tail": (row["log_tail"] or "")[-500:],
    }


def _find_report(asset: str) -> Path | None:
    """找该资产最新报告工件。"""
    base = OUTPUT_DIR / asset
    if not base.exists():
        base = OUTPUT_DIR / asset.replace(" ", "_")
    if not base.exists():
        # 兜底: 全 output 下含资产名的目录
        cands = [p for p in OUTPUT_DIR.glob("*") if p.is_dir() and asset.split()[0] in p.name]
        base = cands[0] if cands else None
    if not base:
        return None
    reports = sorted(base.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


@app.get("/api/v1/research/{task_id}/report")
def task_report(task_id: str):
    with _db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"task {task_id} not found")
    if row["status"] != "done":
        raise HTTPException(409, f"task status={row['status']}, report not ready")
    report = _find_report(row["asset"])
    if not report:
        raise HTTPException(404, "report artifact not found on disk")
    return JSONResponse(
        {
            "research_id": task_id,
            "asset": row["asset"],
            "report_path": str(report),
            "report_markdown": report.read_text(encoding="utf-8", errors="replace")[:100000],
        }
    )


@app.get("/api/v1/research/{task_id}/evidence")
def task_evidence(task_id: str):
    """证据账本端点——Phase A 的账本从 gate 副产物/重算中取。"""
    with _db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"task {task_id} not found")
    report = _find_report(row["asset"])
    if not report:
        raise HTTPException(404, "report not found")
    text = report.read_text(encoding="utf-8", errors="replace")
    try:
        from pipeline.evidence_enforcer import run_evidence_check

        # compute_results 从 lineage/工件重建成本高——服务层用轻量账本（提取+自检）
        ledger = run_evidence_check(text, {"engine_ib": {"status": "skip"}})
        return {
            "research_id": task_id,
            "claims_total": len(ledger.claims),
            "note": "compute_results 不在服务层重算——完整核对账本见报告附录",
            "claims_sample": [{"line": c.line, "text": c.text[:60], "kind": c.kind} for c in ledger.claims[:30]],
        }
    except Exception as e:
        raise HTTPException(500, f"evidence extraction failed: {e}")
