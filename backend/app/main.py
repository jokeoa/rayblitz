import re
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config, jobs

MAX_BYTES = 300 * 1024 * 1024
ALLOWED = {".mov", ".mp4", ".m4v"}
JOB_ID = re.compile(r"^[0-9a-f]{8}$")

app = FastAPI(title="CashGuard")


def check_key(x_api_key: str | None = Header(default=None)) -> None:
    if not x_api_key or not secrets.compare_digest(x_api_key, config.API_KEY):
        raise HTTPException(401, "invalid API key")


async def submit(file: UploadFile) -> dict:
    name = file.filename or "video.mov"
    if Path(name).suffix.lower() not in ALLOWED:
        raise HTTPException(415, "expected .mov or .mp4 file")
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file too large")
    return {"job_id": jobs.create(name, data), "status": "processing"}


def status(job_id: str, full: bool = False) -> dict:
    job = jobs.get(job_id) if JOB_ID.match(job_id) else None
    if not job:
        raise HTTPException(404, "job not found")
    return jobs.public(job, full)


@app.post("/api/v1/analyze", dependencies=[Depends(check_key)])
async def api_analyze(file: UploadFile = File(...)) -> dict:
    return await submit(file)


@app.get("/api/v1/jobs/{job_id}", dependencies=[Depends(check_key)])
async def api_job(job_id: str) -> dict:
    return status(job_id)


@app.post("/ui/analyze")
async def ui_analyze(file: UploadFile = File(...)) -> dict:
    return await submit(file)


@app.get("/ui/jobs/{job_id}")
async def ui_job(job_id: str) -> dict:
    return status(job_id, full=True)


@app.get("/ui/jobs/{job_id}/video")
async def ui_video(job_id: str) -> FileResponse:
    if not JOB_ID.match(job_id):
        raise HTTPException(404)
    files = sorted(jobs.job_dir(job_id).glob("input.*"))
    if not files:
        raise HTTPException(404)
    return FileResponse(files[0], media_type="video/mp4")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if config.CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

if (config.ROOT / "static").is_dir():
    app.mount("/", StaticFiles(directory=config.ROOT / "static", html=True), name="static")
