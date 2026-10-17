import asyncio
import json
import logging
import time
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import httpx

from app import config
from app.analyzers.common import SYSTEM, Event, semaphore, windows
from app.analyzers.probe import LETTERS, frame_content, p_yes, top
from app.video import Frame, sample_frames

log = logging.getLogger("atoms")

ATOMS_PATH = config.ROOT / "rules" / "atoms.json"
PRIME = "Question:"
LOCATE_TOP = 5
LOCATE_MIN = 0.4

TRIGGER = {
    "unattended_valuables": "away",
    "safe_left_open": "safe_open",
    "key_left": "away",
    "workstation_unlocked": "away",
    "documents_left_open": "away",
    "no_id_check": "cash_exchange",
    "client_substitution": "cash_to_client",
    "count_without_client": "machine_count",
    "payout_without_count": "cash_to_client",
    "manual_count": "hand_count",
    "rejected_note_added": "rejected_note",
    "personal_items": "personal_items",
    "phone_use": "phone",
    "food_drink": "food",
    "bag_unchecked": "cash_bag",
    "unauthorized_person": "extra_person",
    "door_left_open": "door_open",
    "cash_concealment": "hand_hidden",
}


@lru_cache
def spec() -> dict:
    return json.loads(ATOMS_PATH.read_text(encoding="utf-8"))


def atoms() -> dict[str, str]:
    return spec()["atoms"]


def user_text() -> str:
    return f"{spec()['intro']}\nI will ask simple yes or no questions about these frames, one at a time."


async def ask(client: httpx.AsyncClient, content: list[dict], prefill: str, **extra) -> dict:
    payload = {
        "model": config.VLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": content + [{"type": "text", "text": user_text()}]},
            {"role": "assistant", "content": prefill},
        ],
        "temperature": 0,
        **config.VLM_EXTRA_BODY,
        **config.VLM_PREFILL_BODY,
        **extra,
    }
    r = await client.post(f"{config.VLM_BASE_URL}/chat/completions", json=payload)
    r.raise_for_status()
    return r.json()["choices"][0]


def yes_no(atom_id: str) -> str:
    return f"{PRIME} {atoms()[atom_id]}\nAnswer yes or no.\nAnswer:"


def when(atom_id: str, n: int) -> str:
    return (f"{PRIME} {atoms()[atom_id]}\nIn which frame (A-{LETTERS[n - 1]}) does this first become true? "
            "Answer with one letter.\nAnswer: Frame")


def rule_scores(seq: list[dict[str, float]]) -> list[dict[str, float]]:
    out = []
    for i, a in enumerate(seq):
        prev = seq[i - 1] if i else a
        seen_id = max(s["id_shown"] for s in seq[:i + 1])
        left_before = max((s["visitor_leaves"] for s in seq[:i]), default=0.0)
        new_visitor = max((min(seq[j]["visitor_leaves"], 1 - max(s["id_shown"] for s in seq[j + 1:i + 1]))
                           for j in range(i)), default=0.0)
        count = max(a["machine_count"], a["hand_count"])
        counted_recently = max(count, prev["machine_count"], prev["hand_count"])
        out.append({
            "unattended_valuables": min(a["away"], a["cash_desk"]),
            "safe_left_open": max(min(a["safe_open"], a["away"]), min(a["safe_open"], prev["safe_open"])),
            "key_left": min(a["key"], a["away"]),
            "workstation_unlocked": min(a["screen_work"], a["away"]),
            "documents_left_open": min(a["docs_desk"], a["away"]),
            "no_id_check": min(a["cash_exchange"], 1 - seen_id),
            "client_substitution": min(a["cash_to_client"], new_visitor),
            "count_without_client": min(count, 1 - a["client_present"], left_before),
            "payout_without_count": max(min(a["cash_to_client"], 1 - counted_recently),
                                        min(a["part_separated"], a["cash_to_client"])),
            "manual_count": min(a["hand_count"], 1 - a["machine_count"]),
            "rejected_note_added": a["rejected_note"],
            "personal_items": a["personal_items"],
            "phone_use": a["phone"],
            "food_drink": a["food"],
            "bag_unchecked": min(a["cash_bag"], a["visitor_leaves"]),
            "unauthorized_person": a["extra_person"],
            "door_left_open": min(a["door_open"], prev["door_open"]),
            "cash_concealment": a["hand_hidden"],
        })
    return [{r: round(v, 4) for r, v in s.items()} for s in out]


async def first_frame(client: httpx.AsyncClient, content: list[dict], chunk: list[Frame], atom_id: str) -> float:
    lp = top(await ask(client, content, when(atom_id, len(chunk)), max_tokens=1, logprobs=True, top_logprobs=20))
    score = lambda i: max(lp.get(LETTERS[i], -1e9), lp.get(" " + LETTERS[i], -1e9))
    return chunk[max(range(len(chunk)), key=score)].t


async def scan_window(client: httpx.AsyncClient, chunk: list[Frame]) -> dict:
    content = frame_content(chunk)
    probs = {}
    async with semaphore():
        await ask(client, content, PRIME, max_tokens=1)
        for atom_id in atoms():
            choice = await ask(client, content, yes_no(atom_id), max_tokens=1, logprobs=True, top_logprobs=10)
            probs[atom_id] = round(p_yes(choice), 4)
        triggers = sorted({a for a in TRIGGER.values() if probs[a] >= LOCATE_MIN}, key=lambda a: -probs[a])[:LOCATE_TOP]
        located = {a: await first_frame(client, content, chunk, a) for a in triggers}
    return {"start": chunk[0].t, "end": chunk[-1].t, "mid": chunk[len(chunk) // 2].t, "atoms": probs, "located": located}


async def analyze(video: Path, work_dir: Path, progress=None, deadline: float | None = None,
                  candidate: float | None = None) -> list[Event]:
    candidate = config.CANDIDATE if candidate is None else candidate
    frames = await asyncio.to_thread(sample_frames, video, work_dir / "frames", config.SAMPLE_FPS, config.FRAME_WIDTH)
    chunks = windows(frames, config.SAMPLE_FPS, config.WINDOW_SEC, config.STRIDE_SEC)
    done = 0

    async with httpx.AsyncClient(timeout=config.VLM_TIMEOUT) as client:
        async def run(chunk):
            nonlocal done
            res = await scan_window(client, chunk)
            done += 1
            if progress:
                progress(done / len(chunks))
            return res

        tasks = [asyncio.create_task(run(c)) for c in chunks]
        timeout = max(1.0, deadline - time.time()) if deadline else None
        finished, pending = await asyncio.wait(tasks, timeout=timeout)
        for t in pending:
            t.cancel()
        if pending:
            log.warning("deadline reached: %d of %d windows skipped", len(pending), len(chunks))
        scanned = sorted((t.result() for t in tasks if t in finished), key=lambda w: w["start"])

    windows_out = [{**w, "probs": s} for w, s in zip(scanned, rule_scores([w["atoms"] for w in scanned]))]
    events = [Event(r, w["located"].get(TRIGGER[r], w["mid"]), s, "", w["start"], w["end"])
              for w in windows_out for r, s in w["probs"].items() if s >= candidate]
    (work_dir / "raw_probs.json").write_text(json.dumps(windows_out, indent=1), encoding="utf-8")
    (work_dir / "raw_events.json").write_text(json.dumps([asdict(e) for e in events], ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    return events
