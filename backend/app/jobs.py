import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

from app import config, overview, pipeline

log = logging.getLogger("jobs")

_jobs: dict[str, dict] = {}
_sem: asyncio.Semaphore | None = None
_tasks: set[asyncio.Task] = set()


def job_dir(job_id: str) -> Path:
    return config.RUNS_DIR / "jobs" / job_id


def create(filename: str, data: bytes, *, created: float | None = None) -> str:
    job_id = uuid.uuid4().hex[:8]
    d = job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    video = d / ("input" + (Path(filename).suffix.lower() or ".mov"))
    video.write_bytes(data)
    _jobs[job_id] = {"job_id": job_id, "status": "processing", "progress": 0.0, "filename": filename,
                     "video": str(video), "created": time.time() if created is None else created, "queued": True, "stage": 0}
    save(_jobs[job_id])
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
        async with asyncio.timeout(max(0, job["created"] + config.JOB_LIMIT_SEC - time.time())), _sem:
            job["queued"] = False
            result = await pipeline.run(
                Path(job["video"]), job_dir(job_id), lambda p: job.update(progress=round(p, 2)),
                deadline=job["created"] + config.DEADLINE_SEC,
            )
            job.update(stage=1, progress=0.0)
            try:
                result["overview"] = await overview.generate(result)
            except Exception:
                log.exception("job %s overview failed", job_id)
                job.update(status="failed", error={"code": "OVERVIEW_GENERATION_FAILED",
                                                  "message": "Не удалось подготовить обзор результатов."})
                return
        job.update(result, status="done", progress=1.0, elapsed_sec=round(time.time() - job["created"], 1))
    except asyncio.TimeoutError:
        log.error("job %s exceeded %.0f s", job_id, config.JOB_LIMIT_SEC)
        job.update(status="failed", queued=False, error={"code": "PROCESSING_TIMEOUT", "message": "Анализ не уложился в лимит времени."})
    except Exception:
        log.exception("job %s failed", job_id)
        job.update(status="failed", queued=False, error={"code": "ANALYSIS_FAILED", "message": "Не удалось выполнить анализ видео."})
    finally:
        save(job)


def save(job: dict) -> None:
    target = job_dir(job["job_id"]) / "result.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)


def get(job_id: str) -> dict | None:
    if job_id in _jobs:
        return _jobs[job_id]
    f = job_dir(job_id) / "result.json"
    if f.exists():
        job = json.loads(f.read_text(encoding="utf-8"))
        if job["status"] == "processing":
            job.update(status="failed", queued=False, error={"code": "ANALYSIS_FAILED",
                       "message": "Обработка прервана перезапуском сервиса."})
            save(job)
        return job
    return None
