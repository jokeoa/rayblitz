import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

from app import config, pipeline

log = logging.getLogger("jobs")

API_FIELDS = ("type", "timecode_sec", "description", "evidence_frames")

_jobs: dict[str, dict] = {}
_sem: asyncio.Semaphore | None = None
_tasks: set[asyncio.Task] = set()


def job_dir(job_id: str) -> Path:
    return config.RUNS_DIR / "jobs" / job_id


def create(filename: str, data: bytes) -> str:
    job_id = uuid.uuid4().hex[:8]
    d = job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    video = d / ("input" + (Path(filename).suffix.lower() or ".mov"))
    video.write_bytes(data)
    _jobs[job_id] = {"job_id": job_id, "status": "processing", "progress": 0.0, "filename": filename,
                     "video": str(video), "created": time.time()}
    task = asyncio.create_task(_run(job_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return job_id


async def _run(job_id: str) -> None:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(config.MAX_JOBS)
    job = _jobs[job_id]
    try:
        async with _sem:
            result = await asyncio.wait_for(
                pipeline.run(Path(job["video"]), job_dir(job_id), lambda p: job.update(progress=round(p, 2)),
                             deadline=job["created"] + config.DEADLINE_SEC),
                timeout=max(1.0, job["created"] + config.JOB_LIMIT_SEC - time.time()),
            )
        job.update(result, status="done", progress=1.0, elapsed_sec=round(time.time() - job["created"], 1))
    except asyncio.TimeoutError:
        log.error("job %s exceeded %.0f s", job_id, config.JOB_LIMIT_SEC)
        job.update(status="failed", error="анализ не уложился в лимит времени")
    except Exception as exc:
        log.exception("job %s failed", job_id)
        job.update(status="failed", error=str(exc))
    (job_dir(job_id) / "result.json").write_text(json.dumps(public(job, full=True), ensure_ascii=False), encoding="utf-8")


def get(job_id: str) -> dict | None:
    if job_id in _jobs:
        return _jobs[job_id]
    f = job_dir(job_id) / "result.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return None


def public(job: dict, full: bool = False) -> dict:
    out = {"job_id": job["job_id"], "status": job["status"]}
    if job["status"] == "processing":
        out["progress"] = job.get("progress", 0.0)
    elif job["status"] == "done":
        out["verdict"] = job["verdict"]
        out["violations"] = job["violations"] if full else [{k: v[k] for k in API_FIELDS} for v in job["violations"]]
        if full:
            out["elapsed_sec"] = job.get("elapsed_sec")
    else:
        out["error"] = job.get("error")
    return out
