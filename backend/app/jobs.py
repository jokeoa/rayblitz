"""Durable file-backed jobs, bounded GPU queue and atomic progress snapshots."""
import asyncio
import json
import logging
import subprocess
import time
import uuid
import threading
from pathlib import Path

from app import config, overview, pipeline, role_context

log = logging.getLogger('jobs')
_jobs: dict[str, dict] = {}
_sem: asyncio.Semaphore | None = None
_preview_sem: asyncio.Semaphore | None = None
_tasks: set[asyncio.Task] = set()
_save_lock = threading.Lock()


def job_dir(job_id):
    return config.RUNS_DIR / 'jobs' / job_id


def save(job):
    target = job_dir(job['job_id']) / 'result.json'
    temporary = target.with_suffix('.tmp')
    with _save_lock:
        temporary.write_text(json.dumps(job, ensure_ascii=False))
        temporary.replace(target)


def schedule(job_id):
    task = asyncio.create_task(_run(job_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def create(filename, data, *, created=None):
    job_id = uuid.uuid4().hex[:8]
    directory = job_dir(job_id)
    directory.mkdir(parents=True)
    video = directory / ('input' + Path(filename).suffix.lower())
    video.write_bytes(data)
    job = {'job_id': job_id, 'status': 'processing', 'progress': 0., 'stage': 0,
           'queued': True, 'filename': filename, 'size_bytes': len(data), 'video': str(video),
           'created': time.time() if created is None else created}
    _jobs[job_id] = job
    save(job)
    schedule(job_id)
    return job_id


def recover():
    for file in (config.RUNS_DIR / 'jobs').glob('*/result.json'):
        job = json.loads(file.read_text())
        _jobs[job['job_id']] = job
        if job['status'] == 'processing':
            job.update(queued=True, stage=0, progress=0.)
            save(job)
            schedule(job['job_id'])


def stage_progress(job, stage, value):
    job.update(stage=stage, progress=round(value, 3))
    save(job)


def preview(video, directory):
    target = directory / 'playback.mp4'
    if target.exists():
        return
    temporary = directory / 'playback.tmp.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video), '-an',
                    '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-crf', '23',
                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(temporary)], check=True, timeout=120)
    temporary.replace(target)


def inspect_video(video, directory, progress):
    from app.vision.runtime import analyze
    return analyze(video, directory, progress)


async def _run(job_id):
    global _sem, _preview_sem
    if _sem is None:
        _sem = asyncio.Semaphore(config.MAX_JOBS)
    if _preview_sem is None:
        _preview_sem = asyncio.Semaphore(2)
    job = _jobs[job_id]
    cancelled = threading.Event()

    def vision_progress(value):
        if cancelled.is_set():
            raise TimeoutError('Vision job cancelled')
        stage_progress(job, 0, value)
    try:
        video, directory = Path(job['video']), job_dir(job_id)
        async with _preview_sem:
            await asyncio.to_thread(preview, video, directory)
        async with _sem:
            job.update(queued=False, started=time.time())
            save(job)
            async with asyncio.timeout(config.JOB_LIMIT_SEC):
                people, objects = await asyncio.to_thread(inspect_video, video, directory,
                    vision_progress)
                token = role_context.current.set(people)
                objects_token = role_context.objects.set(objects)
                try:
                    stage_progress(job, 1, 0.)
                    result = await pipeline.run(video, directory, lambda p: stage_progress(job, 1, p),
                                                deadline=job['started'] + config.DEADLINE_SEC)
                finally:
                    role_context.current.reset(token)
                    role_context.objects.reset(objects_token)
                result['limitations'].append(objects['limitation'])
                if people['geometry']['basis'] == 'uncalibrated':
                    result['limitations'].append('Геометрия сцены не подтверждена. Привязка роли к стороне стола недоступна.')
                stage_progress(job, 2, 0.)
                try:
                    result['overview'] = await overview.generate(result)
                except Exception:
                    log.exception('job %s overview failed', job_id)
                    job.update(status='failed', error={'code': 'OVERVIEW_GENERATION_FAILED',
                                                      'message': 'Не удалось подготовить обзор результатов.'})
                    return
            job.update(result, status='done', progress=1., elapsed_sec=round(time.time()-job['started'], 1))
    except asyncio.TimeoutError:
        job.update(status='failed', queued=False, error={'code': 'PROCESSING_TIMEOUT',
                                                       'message': 'Анализ не уложился в лимит времени.'})
    except asyncio.CancelledError:
        job.update(queued=True)
        raise
    except Exception:
        log.exception('job %s failed', job_id)
        job.update(status='failed', queued=False, error={'code': 'ANALYSIS_FAILED',
                                                       'message': 'Не удалось выполнить анализ видео.'})
    finally:
        cancelled.set()
        save(job)


def get(job_id):
    if job_id in _jobs:
        return _jobs[job_id]
    file = job_dir(job_id) / 'result.json'
    return json.loads(file.read_text()) if file.exists() else None


def history():
    from app.payloads import progress
    ids = set(_jobs) | {p.parent.name for p in (config.RUNS_DIR / 'jobs').glob('*/result.json')}
    result = []
    for job_id in ids:
        job = get(job_id)
        result.append({'jobId': job_id, 'fileName': job['filename'], 'sizeBytes': job['size_bytes'],
                       'createdAt': job['created']*1000, 'startedAt': job.get('started', 0)*1000 or None,
                       'queued': job.get('queued', False), 'playbackReady': (job_dir(job_id) / 'playback.mp4').exists(), 'status': job['status'],
                       'percent': progress(job)['percent'],
                       **({'verdict': job['verdict'], 'violationsCount': len(job['violations'])} if job['status'] == 'done' else {}),
                       **({'errorCode': job['error']['code']} if job['status'] == 'failed' else {})})
    return sorted(result, key=lambda j: j['createdAt'], reverse=True)
