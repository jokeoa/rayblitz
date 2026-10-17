import asyncio
import json
import logging
import time
from pathlib import Path

from app import config, detector, rules
from app.analyzers import facts, probe as analyzer
from app.analyzers.common import Event
from app.video import Frame, b64, frame_jpeg, probe

log = logging.getLogger("pipeline")

DESCRIBE_RESERVE_SEC = 25
DETECT_RESERVE_SEC = 30


def merge(events: list[Event], gap: float) -> list[tuple[Event, int]]:
    groups: list[list[Event]] = []
    for e in sorted(events, key=lambda e: (e.rule_id, e.t)):
        if groups and groups[-1][-1].rule_id == e.rule_id and e.t - groups[-1][-1].t <= gap:
            groups[-1].append(e)
        else:
            groups.append([e])
    picked = [(max(g, key=lambda e: (e.confidence, -e.t)), len(g)) for g in groups]
    return sorted(picked, key=lambda p: p[0].t)


def thresholds() -> dict[str, float]:
    f = config.THRESHOLDS_PATH
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def decide(events: list[Event], threshold: float, per_rule: dict[str, float] | None = None) -> list[tuple[Event, int]]:
    per_rule = per_rule or {}
    return [(e, n) for e, n in merge(events, config.MERGE_SEC) if e.confidence >= per_rule.get(e.rule_id, threshold)]


def gated(events: list[Event], ev: dict, samples: list[dict]) -> list[Event]:
    out = []
    for e in events:
        if e.rule_id in config.COMPOSITE_RULES:
            continue
        if e.rule_id in detector.LEAVE_RULES:
            allowed, t = detector.gate(ev, e.window_start, e.window_end)
            if not allowed:
                continue
            if t is not None:
                e.t = t
        out.append(e)
    for rule_id, (p, t) in facts.composite(samples, ev).items():
        if rule_id in config.COMPOSITE_RULES:
            out.append(Event(rule_id, t, p, "", t, t))
    return out


async def detected(video: Path, work_dir: Path, events: list[Event], duration: float) -> list[Event]:
    files = sorted((work_dir / "frames").glob("*.jpg"))
    frames = [Frame(i, round(i / config.SAMPLE_FPS, 2), p) for i, p in enumerate(files)]
    rows = await asyncio.to_thread(detector.detect, frames)
    ev = detector.events(rows)
    windows = [(e.rule_id, e.window_start, e.window_end) for e in events if e.rule_id in facts.HANDS]
    samples = await facts.facts(video, rows, ev, duration, config.COMPOSITE_RULES, windows)
    (work_dir / "events.json").write_text(json.dumps(ev), encoding="utf-8")
    (work_dir / "facts.json").write_text(json.dumps(samples), encoding="utf-8")
    return gated(events, ev, samples)


def evidence(video: Path, t: float, duration: float) -> list[dict]:
    times = [t] + [x for x in (t - 1.0, t + 1.0) if 0 <= x < duration]
    return [{"timestamp_sec": round(x, 2), "image_base64": b64(frame_jpeg(video, x))} for x in times]


def violation(video: Path, e: Event, support: int, duration: float) -> dict:
    r = rules.rule(e.rule_id)
    return {
        "type": r["type"],
        "timecode_sec": round(e.t, 1),
        "description": f"{e.observation} Основание: {rules.citation_text(e.rule_id)}",
        "evidence_frames": evidence(video, e.t, duration),
        "rule": rules.citation(e.rule_id),
        "confidence": round(e.confidence, 2),
        "support": support,
    }


async def run(video: Path, work_dir: Path, progress=None, deadline: float | None = None) -> dict:
    duration = (await asyncio.to_thread(probe, video))["duration"]
    use_detector = config.DETECTOR != "off"
    reserve = DESCRIBE_RESERVE_SEC + (DETECT_RESERVE_SEC if use_detector else 0)
    scan_deadline = deadline - reserve if deadline else None
    scan_progress = 0.0
    limitations = []

    def scanned(value):
        nonlocal scan_progress
        scan_progress = value
        if progress:
            progress(value * .8)

    events = await analyzer.analyze(video, work_dir, scanned, deadline=scan_deadline)
    if scan_progress < 1:
        limitations.append("Часть окон видео не обработана из-за ограничения времени.")
    if use_detector:
        budget = max(1.0, deadline - DESCRIBE_RESERVE_SEC - time.time()) if deadline else None
        try:
            events = await asyncio.wait_for(detected(video, work_dir, events, duration), timeout=budget)
        except asyncio.TimeoutError:
            limitations.append("Проверка детектором не завершена в отведённое время.")
            log.warning("detector stage hit the deadline, keeping scan events only")
            events = [e for e in events if e.rule_id not in config.COMPOSITE_RULES]
    if progress:
        progress(.9)
    picked = decide(events, config.THRESHOLD, thresholds())
    for e, _ in picked:
        if deadline and time.time() > deadline - 10:
            e.observation = f"Зафиксирован признак: {rules.rule(e.rule_id)['type'].lower()}."
        else:
            e.observation = await analyzer.describe(work_dir, e)
    violations = [await asyncio.to_thread(violation, video, e, n, duration) for e, n in picked]
    return {"verdict": "violation" if violations else "no_violation", "violations": violations, "limitations": limitations}
