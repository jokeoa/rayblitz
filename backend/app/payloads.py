"""HTTP projections of internal analysis results; frontend contracts are authoritative."""

API_FIELDS = ("type", "timecode_sec", "description", "evidence_frames")
STAGES = (
    ("vision", "Люди и предметы", "Отслеживаем людей, закрепляем роли и наблюдаем предметы на столе."),
    ("analysis", "Анализ видео", "Ищем события и подготавливаем кадры-доказательства."),
    ("overview", "Подготовка обзора", "Локальная модель обобщает результаты анализа."),
)


def progress(job: dict) -> dict:
    active = job.get("stage", 0)
    percent = min(99, max(0, job.get("progress", 0) * 100))
    stages = []
    for i, (id_, label, description) in enumerate(STAGES):
        state = ("done" if job["status"] == "done" or i < active else
                 "pending" if i > active or job.get("queued", False) else
                 "failed" if job["status"] == "failed" else "running")
        stages.append(dict(id=id_, label=label, description=description, status=state,
                           percent=100 if state == "done" else percent if i == active and state != "pending" else 0))
    overall = 100 if job["status"] == "done" else (active + percent/100) / len(STAGES) * 100
    return {"percent": round(overall, 2), "stages": stages}


def job_response(job: dict, view: str = "jury") -> dict:
    out = {"job_id": job["job_id"], "status": job["status"]}
    if view == "ui":
        out["progress"] = progress(job)
    if job["status"] == "done":
        out["verdict"] = job["verdict"]
        if view == "ui":
            out.update(overview=job["overview"], violations_count=len(job["violations"]))
        else:
            out["violations"] = [{k: v[k] for k in API_FIELDS} for v in job["violations"]]
    elif job["status"] == "failed":
        out["error"] = job["error"]
    return out


def ordered_violations(job: dict) -> list[dict]:
    return sorted(job["violations"], key=lambda v: v["timecode_sec"])


def violations_page(job: dict, page: int, page_size: int) -> dict:
    items = []
    for i, v in enumerate(ordered_violations(job)):
        rule = v["rule"]
        items.append({
            "id": f"v{i:06d}", **{k: v[k] for k in API_FIELDS if k != "evidence_frames"},
            "rule": {"text": rule["requirement"], "sources": [{
                "document_title": rule["document"], "section": rule["clause"], "url": rule["url"]}]},
            "evidence_frames": [{"frame_id": f"f{n}", "timestamp_sec": f["timestamp_sec"]}
                                for n, f in enumerate(v["evidence_frames"])],
        })
    start = (page - 1) * page_size
    return dict(job_id=job["job_id"], items=items[start:start + page_size], page=page,
                page_size=page_size, total=len(items))
