"""2hao-analyst Web Workbench — Enhanced FastAPI + HTMX + SSE.

Run: python -m web.app
Then open http://localhost:8000
"""

import asyncio
import json
import os
import shutil
import sqlite3

# Add project root to path
import sys
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from main import run_pipeline


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: str
    asset: str
    report_type: str
    style: str
    requirement: str
    human_gate: bool
    output_dir: str
    status: JobStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int = 0
    stage: str = ""
    result: Optional[Dict] = None
    error: Optional[str] = None
    pipeline_stages: Optional[List[Dict]] = None

    def to_dict(self) -> Dict:
        return asdict(self)


# Database setup
DB_PATH = _ROOT / "web_jobs.db"


def init_db():
    """Initialize SQLite database for job persistence."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            asset TEXT NOT NULL,
            report_type TEXT NOT NULL,
            style TEXT NOT NULL,
            requirement TEXT,
            human_gate BOOLEAN DEFAULT 0,
            output_dir TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            progress INTEGER DEFAULT 0,
            stage TEXT,
            result TEXT,
            error TEXT,
            pipeline_stages TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC)")
    conn.commit()
    conn.close()


def save_job(job: Job):
    """Save job to database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT OR REPLACE INTO jobs
        (id, asset, report_type, style, requirement, human_gate, output_dir,
         status, created_at, started_at, completed_at, progress, stage,
         result, error, pipeline_stages)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            job.id,
            job.asset,
            job.report_type,
            job.style,
            job.requirement,
            job.human_gate,
            job.output_dir,
            job.status.value,
            job.created_at,
            job.started_at,
            job.completed_at,
            job.progress,
            job.stage,
            json.dumps(job.result) if job.result else None,
            job.error,
            json.dumps(job.pipeline_stages) if job.pipeline_stages else None,
        ),
    )
    conn.commit()
    conn.close()


def load_job(job_id: str) -> Optional[Job]:
    """Load job from database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return Job(
        id=row["id"],
        asset=row["asset"],
        report_type=row["report_type"],
        style=row["style"],
        requirement=row["requirement"] or "",
        human_gate=bool(row["human_gate"]),
        output_dir=row["output_dir"] or "",
        status=JobStatus(row["status"]),
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        progress=row["progress"] or 0,
        stage=row["stage"] or "",
        result=json.loads(row["result"]) if row["result"] else None,
        error=row["error"],
        pipeline_stages=json.loads(row["pipeline_stages"]) if row["pipeline_stages"] else None,
    )


def load_jobs(limit: int = 100, status: Optional[JobStatus] = None, asset: Optional[str] = None) -> List[Job]:
    """Load jobs from database with filters."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status.value)
    if asset:
        query += " AND asset LIKE ?"
        params.append(f"%{asset}%")

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    jobs = []
    for row in rows:
        jobs.append(
            Job(
                id=row["id"],
                asset=row["asset"],
                report_type=row["report_type"],
                style=row["style"],
                requirement=row["requirement"] or "",
                human_gate=bool(row["human_gate"]),
                output_dir=row["output_dir"] or "",
                status=JobStatus(row["status"]),
                created_at=row["created_at"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                progress=row["progress"] or 0,
                stage=row["stage"] or "",
                result=json.loads(row["result"]) if row["result"] else None,
                error=row["error"],
                pipeline_stages=json.loads(row["pipeline_stages"]) if row["pipeline_stages"] else None,
            )
        )
    return jobs


# Job queue with worker
class JobQueue:
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self.running = 0
        self.queue: asyncio.Queue = asyncio.Queue()
        self.workers: List[asyncio.Task] = []
        self.cancelled_jobs: set = set()

    async def start(self):
        for i in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)

    async def stop(self):
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)

    async def enqueue(self, job_id: str):
        await self.queue.put(job_id)

    def cancel(self, job_id: str):
        self.cancelled_jobs.add(job_id)

    async def _worker(self, name: str):
        while True:
            try:
                job_id = await self.queue.get()

                if job_id in self.cancelled_jobs:
                    self.cancelled_jobs.discard(job_id)
                    job = load_job(job_id)
                    if job:
                        job.status = JobStatus.CANCELLED
                        job.completed_at = datetime.now().isoformat()
                        save_job(job)
                    continue

                self.running += 1
                await self._run_job(job_id)
                self.running -= 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Worker {name} error: {e}")
                self.running = max(0, self.running - 1)

    async def _run_job(self, job_id: str):
        job = load_job(job_id)
        if not job:
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now().isoformat()
        job.progress = 0
        job.stage = "初始化管线"
        save_job(job)

        try:
            if job.requirement:
                os.environ["CUSTOM_REQUIREMENT"] = job.requirement

            # Pipeline stages for progress tracking
            stages = [
                ("环境验证", 5),
                ("数据采集", 20),
                ("图表生成", 35),
                ("计算引擎", 45),
                ("报告撰写", 65),
                ("风格编译", 75),
                ("IronGate质检", 85),
                ("导出文档", 95),
                ("完成", 100),
            ]
            job.pipeline_stages = [{"name": s[0], "progress": s[1], "completed": False} for s in stages]

            # Simulate progress updates (in real implementation, hook into pipeline callbacks)
            for i, (stage_name, stage_progress) in enumerate(stages):
                if job_id in self.cancelled_jobs:
                    job.status = JobStatus.CANCELLED
                    break

                job.stage = stage_name
                job.progress = stage_progress
                job.pipeline_stages[i]["completed"] = True
                save_job(job)

                # In real implementation, this would be driven by actual pipeline callbacks
                await asyncio.sleep(2)  # Simulate work

            # Run actual pipeline
            result = run_pipeline(
                asset=job.asset,
                report_type=job.report_type,
                style=job.style,
                output_dir=job.output_dir,
            )

            if result.get("status") == "ok":
                job.status = JobStatus.COMPLETED
                job.result = result
            else:
                job.status = JobStatus.FAILED
                job.error = result.get("error", "Pipeline failed")

            # Log to track record
            try:
                from core.tools.track_record import TrackRecordManager

                tm = TrackRecordManager()
                tm.log_run(job.id, job.asset, job.report_type, job.style, result)
            except Exception:
                pass

        except Exception as e:
            job.status = JobStatus.ERROR
            job.error = str(e)
        finally:
            if "CUSTOM_REQUIREMENT" in os.environ:
                del os.environ["CUSTOM_REQUIREMENT"]
            job.completed_at = datetime.now().isoformat()
            job.progress = 100
            save_job(job)


# Global job queue
job_queue = JobQueue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await job_queue.start()
    yield
    await job_queue.stop()


app = FastAPI(title="二号分析师 · 工作台", version="0.11.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory=str(_ROOT / "web" / "static")), name="static")
app.mount("/output", StaticFiles(directory=str(_ROOT / "output")), name="output")
templates = Jinja2Templates(directory=str(_ROOT / "web" / "templates"))


# SSE endpoint for real-time progress
@app.get("/jobs/{job_id}/stream")
async def job_stream(job_id: str):
    """Server-Sent Events for real-time job progress."""

    async def event_generator():
        last_progress = -1
        last_status = None

        while True:
            job = load_job(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            # Send update if changed
            if job.progress != last_progress or job.status != last_status:
                data = {
                    "id": job.id,
                    "status": job.status.value,
                    "progress": job.progress,
                    "stage": job.stage,
                    "pipeline_stages": job.pipeline_stages,
                    "completed_at": job.completed_at,
                }
                yield f"data: {json.dumps(data)}\n\n"
                last_progress = job.progress
                last_status = job.status

            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.ERROR, JobStatus.CANCELLED):
                # Send final update
                yield f"data: {json.dumps({'final': True, 'status': job.status.value})}\n\n"
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# Job management endpoints
@app.post("/jobs", response_class=HTMLResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    request: Request,
    asset: str = Form(...),
    report_type: str = Form("listed_company"),
    style: str = Form("cicc"),
    requirement: str = Form(""),
    human_gate: bool = Form(False),
):
    """Create and enqueue a new report generation job."""
    job_id = str(uuid.uuid4())[:8]
    output_dir = str(_ROOT / "output" / job_id)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    job = Job(
        id=job_id,
        asset=asset,
        report_type=report_type,
        style=style,
        requirement=requirement,
        human_gate=human_gate,
        output_dir=output_dir,
        status=JobStatus.QUEUED,
        created_at=datetime.now().isoformat(),
    )
    save_job(job)

    # Enqueue for processing
    await job_queue.enqueue(job_id)

    return templates.TemplateResponse(
        "job_card.html", {"request": request, "job": job, "stream_url": f"/jobs/{job_id}/stream"}
    )


@app.get("/jobs", response_class=HTMLResponse)
async def list_jobs(
    request: Request,
    status: Optional[str] = Query(None),
    asset: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    page: int = Query(1, ge=1),
):
    """List jobs with filters and pagination."""
    status_enum = JobStatus(status) if status else None
    jobs = load_jobs(limit=limit * page, status=status_enum, asset=asset)

    # Paginate
    start = (page - 1) * limit
    end = start + limit
    paginated = jobs[start:end]

    total = len(load_jobs(limit=10000, status=status_enum, asset=asset))

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "jobs_list_fragment.html",
            {
                "request": request,
                "jobs": paginated,
                "page": page,
                "limit": limit,
                "total": total,
                "has_more": end < total,
                "status_filter": status,
                "asset_filter": asset,
            },
        )

    return templates.TemplateResponse(
        "jobs_list.html",
        {
            "request": request,
            "jobs": paginated,
            "page": page,
            "limit": limit,
            "total": total,
            "has_more": end < total,
            "status_filter": status,
            "asset_filter": asset,
            "statuses": [s.value for s in JobStatus],
        },
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str):
    """Job detail page with full history."""
    job = load_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return templates.TemplateResponse("job_detail.html", {"request": request, "job": job})


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a queued or running job."""
    job = load_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.ERROR, JobStatus.CANCELLED):
        raise HTTPException(400, "Cannot cancel completed job")

    job_queue.cancel(job_id)

    if job.status == JobStatus.QUEUED:
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now().isoformat()
        save_job(job)

    return JSONResponse({"status": "cancelled", "job_id": job_id})


@app.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, background_tasks: BackgroundTasks):
    """Retry a failed job."""
    job = load_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    if job.status not in (JobStatus.FAILED, JobStatus.ERROR, JobStatus.CANCELLED):
        raise HTTPException(400, "Can only retry failed jobs")

    # Create new job with same parameters
    new_job_id = str(uuid.uuid4())[:8]
    new_output_dir = str(_ROOT / "output" / new_job_id)
    Path(new_output_dir).mkdir(parents=True, exist_ok=True)

    new_job = Job(
        id=new_job_id,
        asset=job.asset,
        report_type=job.report_type,
        style=job.style,
        requirement=job.requirement,
        human_gate=job.human_gate,
        output_dir=new_output_dir,
        status=JobStatus.QUEUED,
        created_at=datetime.now().isoformat(),
    )
    save_job(new_job)
    await job_queue.enqueue(new_job_id)

    return JSONResponse({"status": "retrying", "new_job_id": new_job_id})


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its output files."""
    job = load_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # Delete output directory
    try:
        output_path = Path(job.output_dir)
        if output_path.exists():
            shutil.rmtree(output_path)
    except Exception:
        pass

    # Delete from database
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()

    return JSONResponse({"status": "deleted", "job_id": job_id})


# Export endpoints
@app.get("/export/history")
async def export_history(
    format: str = Query("json", regex="^(json|csv)$"),
    status: Optional[str] = None,
    asset: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
):
    """Export job history as JSON or CSV."""
    since = (datetime.now() - timedelta(days=days)).isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM jobs WHERE created_at >= ?"
    params = [since]

    if status:
        query += " AND status = ?"
        params.append(status)
    if asset:
        query += " AND asset LIKE ?"
        params.append(f"%{asset}%")

    query += " ORDER BY created_at DESC"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    data = [dict(row) for row in rows]

    if format == "csv":
        import csv
        from io import StringIO

        output = StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=jobs_export_{datetime.now().strftime('%Y%m%d')}.csv"
            },
        )

    return JSONResponse(data)


# Track record endpoints
@app.get("/track-record", response_class=HTMLResponse)
async def track_record(request: Request):
    try:
        from core.tools.track_record import TrackRecordManager

        tm = TrackRecordManager()
        summary = tm.get_public_summary()
    except Exception as e:
        summary = {"error": str(e), "total_calls": 0, "directional_accuracy": 0, "avg_pnl_pct": 0, "calls": []}

    return templates.TemplateResponse("track_record.html", {"request": request, "summary": summary})


@app.get("/api/track-record")
async def api_track_record():
    try:
        from core.tools.track_record import TrackRecordManager

        tm = TrackRecordManager()
        return tm.get_public_summary()
    except Exception as e:
        return {"error": str(e)}


# Main pages
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main workbench dashboard."""
    # Get stats
    all_jobs = load_jobs(limit=10000)
    stats = {
        "total": len(all_jobs),
        "completed": sum(1 for j in all_jobs if j.status == JobStatus.COMPLETED),
        "running": sum(1 for j in all_jobs if j.status == JobStatus.RUNNING),
        "queued": sum(1 for j in all_jobs if j.status == JobStatus.QUEUED),
        "failed": sum(1 for j in all_jobs if j.status in (JobStatus.FAILED, JobStatus.ERROR)),
    }
    recent_jobs = all_jobs[:10]

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats, "recent_jobs": recent_jobs, "statuses": [s.value for s in JobStatus]},
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "2hao-analyst-web", "version": "0.11.0"}


@app.get("/metrics")
async def metrics():
    try:
        from fastapi import Response

        from core.observability import get_metrics

        return Response(content=get_metrics(), media_type="text/plain")
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════
# S7-1: 工作台路由
# ═══════════════════════════════════════════════

@app.get("/workbench", response_class=HTMLResponse)
async def workbench(request: Request):
    """工作台首页：任务管理、状态总览、快速操作。"""
    return templates.TemplateResponse("workbench.html", {"request": request, "version": "0.11.0"})


# ═══════════════════════════════════════════════
# S7-2: 批次状态 API
# ═══════════════════════════════════════════════

@app.get("/api/batches")
async def list_batches():
    """列出所有批次。"""
    batch_dir = Path(__file__).resolve().parent.parent / "data" / "batches"
    if not batch_dir.exists():
        return {"batches": []}
    batches = []
    for fp in sorted(batch_dir.glob("batch_*.json"), reverse=True):
        try:
            state = json.loads(fp.read_text(encoding="utf-8"))
            batches.append(state)
        except Exception:
            pass
    return {"batches": batches[:20]}


@app.get("/api/batches/{batch_id}")
async def get_batch(batch_id: str):
    """获取单个批次状态。"""
    batch_dir = Path(__file__).resolve().parent.parent / "data" / "batches"
    fp = batch_dir / f"{batch_id}.json"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Batch not found")
    return json.loads(fp.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════
# S7-4: 人工审核路由（Human-in-the-Loop）
# ═══════════════════════════════════════════════

@app.post("/api/review/{job_id}/approve")
async def approve_job(job_id: str):
    """人工批准：允许报告继续导出。"""
    review_dir = Path(__file__).resolve().parent.parent / "data" / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    fp = review_dir / f"{job_id}.json"
    fp.write_text(json.dumps({
        "job_id": job_id,
        "decision": "approved",
        "timestamp": datetime.now().isoformat(),
    }, ensure_ascii=False), encoding="utf-8")
    return {"status": "approved", "job_id": job_id}


@app.post("/api/review/{job_id}/reject")
async def reject_job(job_id: str, reason: str = Form(...)):
    """人工拒绝：标记报告为需修改。"""
    review_dir = Path(__file__).resolve().parent.parent / "data" / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    fp = review_dir / f"{job_id}.json"
    fp.write_text(json.dumps({
        "job_id": job_id,
        "decision": "rejected",
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
    }, ensure_ascii=False), encoding="utf-8")
    return {"status": "rejected", "job_id": job_id}


@app.get("/api/review/{job_id}")
async def get_review(job_id: str):
    """查询审核状态。"""
    review_dir = Path(__file__).resolve().parent.parent / "data" / "reviews"
    fp = review_dir / f"{job_id}.json"
    if not fp.exists():
        return {"status": "pending", "job_id": job_id}
    return json.loads(fp.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
