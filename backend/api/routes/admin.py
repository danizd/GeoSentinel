import asyncio
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter()

SCRIPT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "backend" / "scripts"
SCRIPTS = {
    "usgs": SCRIPT_ROOT / "run_usgs.py",
    "firms": SCRIPT_ROOT / "run_firms.py",
    "gdelt": SCRIPT_ROOT / "run_gdelt.py",
    "acled": SCRIPT_ROOT / "run_acled.py",
    "clustering": SCRIPT_ROOT / "run_clustering.py",
}

JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = asyncio.Lock()


def _get_running_job(job_name: str) -> Optional[dict[str, Any]]:
    for j in JOBS.values():
        if j["job"] == job_name and j["status"] == "running":
            return j
    return None


async def _run_script(script_path: Path) -> dict[str, Any]:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _execute_script, script_path)
    return result


def _execute_script(script_path: Path) -> dict[str, Any]:
    env = {"PYTHONPATH": str(Path(__file__).resolve().parent.parent.parent.parent)}
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        env={**subprocess.os.environ.copy(), **env},
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return {"stdout": result.stdout, "returncode": result.returncode}


async def _run_lifecycle_job() -> dict[str, Any]:
    from backend.jobs.incident_lifecycle import run_lifecycle_job
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = "postgresql://postgres:postgres@localhost:5432/geosentinel"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        result = run_lifecycle_job(session)
    return result


async def _run_clustering_job() -> dict[str, Any]:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _execute_clustering)
    return result


def _execute_clustering() -> dict[str, Any]:
    return _execute_script(SCRIPT_ROOT / "run_clustering.py")


def _parse_script_output(stdout: str, job_name: str) -> dict[str, int]:
    metrics: dict[str, int] = {
        "events_fetched": 0,
        "events_inserted": 0,
        "events_quarantine": 0,
        "incidents_created": 0,
        "incidents_updated": 0,
    }

    line_map = {
        "events_fetched": ["total_fetched", "total_fetched:", "fetched"],
        "events_inserted": ["processed", "processed:"],
        "events_quarantine": ["quarantined", "quarantined:"],
        "incidents_created": ["created", "created:"],
        "incidents_updated": ["updated", "updated:"],
    }

    for line in stdout.split("\n"):
        for metric, keywords in line_map.items():
            for kw in keywords:
                if kw in line.lower():
                    parts = line.strip().split()
                    for i, part in enumerate(parts):
                        if part.rstrip(":") == kw.rstrip(":"):
                            try:
                                value = int(parts[i + 1].rstrip(":"))
                                metrics[metric] = max(metrics[metric], value)
                            except (IndexError, ValueError):
                                pass

    if job_name in ("clustering",):
        for line in stdout.split("\n"):
            for kw in ["created", "assigned", "total_events"]:
                if kw in line.lower():
                    parts = line.strip().split()
                    for i, part in enumerate(parts):
                        if part.rstrip(":") == kw.rstrip(":"):
                            try:
                                value = int(parts[i + 1].rstrip(":"))
                                if "created" in kw:
                                    metrics["incidents_created"] = value
                                elif "assigned" in kw:
                                    metrics["events_inserted"] = value
                                elif "total" in kw:
                                    metrics["events_fetched"] = value
                            except (IndexError, ValueError):
                                pass

    if job_name == "lifecycle":
        for line in stdout.split("\n"):
            if "stale_transition" in line.lower():
                parts = line.strip().split()
                for i, p in enumerate(parts):
                    if "stale" in p.lower() and i + 1 < len(parts):
                        try:
                            metrics["incidents_updated"] = int(parts[i + 1])
                        except ValueError:
                            pass

    return metrics


class JobResponse(BaseModel):
    job: str
    status: str
    started_at: str
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    job: str
    status: str
    started_at: str
    finished_at: Optional[str] = None
    duration_sec: Optional[int] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


def _create_job_record(job_name: str) -> tuple[str, dict[str, Any]]:
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    record = {
        "job_id": job_id,
        "job": job_name,
        "status": "running",
        "started_at": now.isoformat(),
        "finished_at": None,
        "duration_sec": None,
        "result": None,
        "error": None,
    }
    return job_id, record


async def _background_job(job_id: str, job_name: str, task_fn, task_kwargs: Optional[dict[str, Any]] = None):
    async with _JOBS_LOCK:
        JOBS[job_id] = _create_job_record(job_name)[1]

    kwargs = task_kwargs or {}
    try:
        raw = await task_fn(**kwargs)
        if isinstance(raw, dict) and "stdout" in raw:
            result_metrics = _parse_script_output(raw["stdout"], job_name)
        elif isinstance(raw, dict):
            result_metrics = raw
        else:
            result_metrics = {}

        async with _JOBS_LOCK:
            job = JOBS[job_id]
            job["status"] = "completed"
            job["finished_at"] = datetime.now(timezone.utc).isoformat()
            started = datetime.fromisoformat(job["started_at"])
            job["duration_sec"] = int((datetime.now(timezone.utc) - started).total_seconds())
            job["result"] = result_metrics
    except Exception as e:
        async with _JOBS_LOCK:
            job = JOBS[job_id]
            job["status"] = "failed"
            job["finished_at"] = datetime.now(timezone.utc).isoformat()
            started = datetime.fromisoformat(job["started_at"])
            job["duration_sec"] = int((datetime.now(timezone.utc) - started).total_seconds())
            job["error"] = str(e)


def _require_admin():
    pass


@router.post("/admin/run/lifecycle", response_model=JobResponse, status_code=202)
async def run_lifecycle(background_tasks: BackgroundTasks):
    async with _JOBS_LOCK:
        existing = _get_running_job("lifecycle")
        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "job_already_running",
                    "job": "lifecycle",
                    "running_since": existing["started_at"],
                    "job_id": existing["job_id"],
                },
            )

    job_id, record = _create_job_record("lifecycle")

    async with _JOBS_LOCK:
        JOBS[job_id] = record

    background_tasks.add_task(_background_job, job_id, "lifecycle", _run_lifecycle_job)

    return JobResponse(
        job="lifecycle",
        status="running",
        started_at=record["started_at"],
        job_id=job_id,
    )


@router.post("/admin/run/all", response_model=JobResponse, status_code=202)
async def run_all_jobs(background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    record = {
        "job_id": job_id,
        "job": "all",
        "status": "running",
        "started_at": now.isoformat(),
        "finished_at": None,
        "duration_sec": None,
        "result": None,
        "error": None,
    }

    async with _JOBS_LOCK:
        for j in JOBS.values():
            if j["job"] == "all" and j["status"] == "running":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "job_already_running",
                        "job": "all",
                        "running_since": j["started_at"],
                        "job_id": j["job_id"],
                    },
                )
        JOBS[job_id] = record

    async def run_all():
        results = {}
        sources = ["usgs", "firms", "gdelt", "acled"]
        tasks = [_run_script(SCRIPTS[s]) for s in sources]
        src_results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, res in enumerate(src_results):
            src = sources[i]
            if isinstance(res, Exception):
                results[src] = {"error": str(res)}
            else:
                results[src] = _parse_script_output(res["stdout"], src)

        cluster_result = await _run_clustering_job()
        if isinstance(cluster_result, Exception):
            results["clustering"] = {"error": str(cluster_result)}
        else:
            results["clustering"] = _parse_script_output(cluster_result["stdout"], "clustering")

        lifecycle_result = await _run_lifecycle_job()
        if isinstance(lifecycle_result, Exception):
            results["lifecycle"] = {"error": str(lifecycle_result)}
        else:
            results["lifecycle"] = lifecycle_result

        total_events = 0
        total_inserted = 0
        total_quarantine = 0
        total_created = 0
        total_updated = 0

        for src in sources:
            r = results.get(src, {})
            total_events += r.get("events_fetched", 0)
            total_inserted += r.get("events_inserted", 0)
            total_quarantine += r.get("events_quarantine", 0)
        total_created = results.get("clustering", {}).get("incidents_created", 0)
        total_updated = results.get("lifecycle", {}).get("incidents_updated", 0)

        return {
            "events_fetched": total_events,
            "events_inserted": total_inserted,
            "events_quarantine": total_quarantine,
            "incidents_created": total_created,
            "incidents_updated": total_updated,
            "details": results,
        }

    background_tasks.add_task(_background_job, job_id, "all", run_all)

    return JobResponse(
        job="all",
        status="running",
        started_at=record["started_at"],
        job_id=job_id,
    )


@router.post("/admin/run/{source}", response_model=JobResponse, status_code=202)
async def run_single_job(source: str, background_tasks: BackgroundTasks):
    if source not in SCRIPTS:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")

    async with _JOBS_LOCK:
        existing = _get_running_job(source)
        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "job_already_running",
                    "job": source,
                    "running_since": existing["started_at"],
                    "job_id": existing["job_id"],
                },
            )

    job_id, record = _create_job_record(source)

    async with _JOBS_LOCK:
        JOBS[job_id] = record

    async def task():
        return await _run_script(SCRIPTS[source])

    background_tasks.add_task(_background_job, job_id, source, task)

    return JobResponse(
        job=source,
        status="running",
        started_at=record["started_at"],
        job_id=job_id,
    )


@router.get("/admin/run/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    async with _JOBS_LOCK:
        job = JOBS.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job["job_id"],
        job=job["job"],
        status=job["status"],
        started_at=job["started_at"],
        finished_at=job.get("finished_at"),
        duration_sec=job.get("duration_sec"),
        result=job.get("result"),
        error=job.get("error"),
    )