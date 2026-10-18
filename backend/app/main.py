import asyncio
import base64
import re
import secrets
import subprocess
import tempfile
import time
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field

from app import config, jobs, payloads
from app.video import probe

MAX_BYTES = 100 * 1024 * 1024
ALLOWED = {".mov"}
JOB_ID = re.compile(r"^[0-9a-f]{8}$")
@asynccontextmanager
async def lifespan(app):
    jobs.recover()
    yield
    for task in list(jobs._tasks):
        task.cancel()
    await asyncio.gather(*jobs._tasks, return_exceptions=True)


app = FastAPI(title="CashGuard", lifespan=lifespan)


def fail(status: int, code: str, message: str):
    raise HTTPException(status, {"code": code, "message": message})


@app.middleware("http")
async def no_store(request: Request, call_next):
    request.state.received_at = time.time()
    if request.url.path.startswith("/api/v1/"):
        key = request.headers.get("x-api-key", "")
        if not secrets.compare_digest(key, config.API_KEY):
            return JSONResponse({"error": {"code": "UNAUTHORIZED", "message": "Неверный или отсутствующий API-ключ."}},
                                status_code=401, headers={"Cache-Control": "no-store"})
    if request.url.path == "/api/v1/analyze" and request.method == "POST":
        if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
            return JSONResponse({"error": {"code": "UNSUPPORTED_MEDIA_TYPE", "message": "Ожидается multipart/form-data."}},
                                status_code=415, headers={"Cache-Control": "no-store"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    error = exc.detail if isinstance(exc.detail, dict) else {"code": "BAD_REQUEST", "message": str(exc.detail)}
    return JSONResponse({"error": error}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse({"error": {"code": "BAD_REQUEST", "message": "Некорректный запрос."}}, status_code=400)


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    return JSONResponse({"error": {"code": "INTERNAL_ERROR", "message": "Внутренняя ошибка сервиса."}}, status_code=500)


def check_key(x_api_key: str | None = Header(default=None)) -> None:
    if not x_api_key or not secrets.compare_digest(x_api_key, config.API_KEY):
        fail(401, "UNAUTHORIZED", "Неверный или отсутствующий API-ключ.")


def query(request: Request, allowed: set[str]) -> dict:
    pairs = list(request.query_params.multi_items())
    if len(dict(pairs)) != len(pairs) or any(k not in allowed for k, _ in pairs):
        fail(400, "BAD_REQUEST", "Некорректные параметры запроса.")
    return dict(pairs)


def get_job(job_id: str, completed=False) -> dict:
    job = jobs.get(job_id) if JOB_ID.fullmatch(job_id) else None
    if not job:
        fail(404, "JOB_NOT_FOUND", "Задача не найдена.")
    if completed and job["status"] != "done":
        fail(409, "JOB_NOT_DONE", "Анализ ещё не завершён.")
    return job


@app.post("/api/v1/analyze", dependencies=[Depends(check_key)], status_code=202)
async def analyze(request: Request, file: UploadFile = File(...)):
    query(request, set())
    form = await request.form()
    if list(form.keys()) != ["file"] or len(form.getlist("file")) != 1 or not file.filename:
        fail(400, "BAD_REQUEST", "Нужно одно поле file с файлом.")
    name = file.filename
    if Path(name).suffix.lower() not in ALLOWED:
        fail(415, "UNSUPPORTED_MEDIA_TYPE", "Принимаются только файлы .mov.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        fail(413, "FILE_TOO_LARGE", "Размер видео превышает 100 MiB.")
    if not data:
        fail(422, "INVALID_VIDEO", "Пустой видеофайл.")
    # Probe the temporary upload before accepting a job; inference has not started yet.
    with tempfile.NamedTemporaryFile(suffix=Path(name).suffix) as video:
        video.write(data)
        video.flush()
        try:
            metadata = await asyncio.to_thread(probe, Path(video.name))
            if metadata["duration"] <= 0:
                raise ValueError("empty video")
        except (ValueError, KeyError, IndexError, subprocess.CalledProcessError):
            fail(422, "INVALID_VIDEO", "Не удалось прочитать видеопоток.")
    job_id = jobs.create(name, data, created=request.state.received_at)
    return JSONResponse({"job_id": job_id}, status_code=202,
                        headers={"Location": f"/api/v1/jobs/{job_id}", "Retry-After": "2"})


@app.get("/api/v1/jobs/{job_id}", dependencies=[Depends(check_key)])
async def job(request: Request, job_id: str):
    view = query(request, {"view"}).get("view", "jury")
    if view not in {"jury", "ui"}:
        fail(400, "BAD_REQUEST", "Неизвестное представление результата.")
    return payloads.job_response(get_job(job_id), view)


@app.get('/api/v1/jobs', dependencies=[Depends(check_key)])
async def history(request: Request):
    query(request, set())
    return {'items': jobs.history()}


@app.get('/api/v1/jobs/{job_id}/video', dependencies=[Depends(check_key)])
async def video(request: Request, job_id: str):
    query(request, set())
    get_job(job_id)
    path = jobs.job_dir(job_id) / 'playback.mp4'
    if not path.exists():
        fail(409, 'JOB_NOT_DONE', 'Видео подготавливается к просмотру.')
    return FileResponse(path, media_type='video/mp4')


@app.get('/api/v1/jobs/{job_id}/observations', dependencies=[Depends(check_key)])
async def observations(request: Request, job_id: str):
    query(request, set())
    get_job(job_id)
    directory = jobs.job_dir(job_id)
    result = {'people': None, 'objects': None}
    for name in result:
        path = directory / f'{name}.json'
        if path.exists():
            result[name] = json.loads(path.read_text())
    return result


class Review(BaseModel):
    reviewed: bool = False
    notes: str = Field(default='', max_length=8000)


@app.get('/api/v1/jobs/{job_id}/review', dependencies=[Depends(check_key)])
async def get_review(request: Request, job_id: str):
    query(request, set())
    get_job(job_id)
    path = jobs.job_dir(job_id) / 'review.json'
    return json.loads(path.read_text()) if path.exists() else Review().model_dump()


@app.put('/api/v1/jobs/{job_id}/review', dependencies=[Depends(check_key)])
async def put_review(request: Request, job_id: str, body: Review):
    query(request, set())
    get_job(job_id)
    path = jobs.job_dir(job_id) / 'review.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(body.model_dump_json())
    temporary.replace(path)
    return body


@app.get("/api/v1/jobs/{job_id}/violations", dependencies=[Depends(check_key)])
async def violations(request: Request, job_id: str):
    params = query(request, {"page", "page_size"})
    values = []
    for key, default, limit in (("page", "1", 1_000_000), ("page_size", "20", 100)):
        value = params.get(key, default)
        if not re.fullmatch(r"[0-9]+", value) or len(value) > 7 or not 1 <= int(value) <= limit:
            fail(400, "BAD_REQUEST", "Некорректная пагинация.")
        values.append(int(value))
    return payloads.violations_page(get_job(job_id, completed=True), *values)


@app.get("/api/v1/jobs/{job_id}/violations/{violation_id}/frames/{frame_id}", dependencies=[Depends(check_key)])
async def frame(request: Request, job_id: str, violation_id: str, frame_id: str):
    query(request, set())
    completed = get_job(job_id, completed=True)
    for i, violation in enumerate(payloads.ordered_violations(completed)):
        if violation_id == f"v{i:06d}":
            for n, evidence in enumerate(violation["evidence_frames"]):
                if frame_id == f"f{n}":
                    return Response(base64.b64decode(evidence["image_base64"], validate=True), media_type="image/jpeg")
    fail(404, "EVIDENCE_NOT_FOUND", "Кадр не найден.")


@app.get("/api/v1/health", dependencies=[Depends(check_key)])
async def health(request: Request):
    query(request, set())
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{config.VLM_BASE_URL.removesuffix('/v1')}/health")
            response.raise_for_status()
        gpu = {"status": "ok", "message": "Сервис модели доступен."}
    except httpx.HTTPError:
        gpu = {"status": "error", "message": "Сервис модели недоступен."}
    healthy = gpu["status"] == "ok"
    return JSONResponse({"status": "ok" if healthy else "degraded",
                         "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                         "services": {"backend": {"status": "ok", "message": "Бэкенд доступен."},
                                      "gpu_server": gpu}}, status_code=200 if healthy else 503)


if config.CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
