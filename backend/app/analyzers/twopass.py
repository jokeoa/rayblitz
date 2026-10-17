import asyncio
import json
import logging
import re
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from app import config, rules
from app.analyzers import probe
from app.analyzers.common import SYSTEM, Event, semaphore
from app.video import Frame, probe as video_info, sample_segment

log = logging.getLogger("twopass")

SCAN_MIN = 0.05
MAX_CANDIDATES = 16
MAX_SPAN_SEC = 16.0
TIMELINE_CHUNK = 24
VERIFY_FPS = 2.0
VERIFY_WIDTH = 464
VERIFY_FRAMES = 16
VERIFY_RESERVE_SEC = 60

ACTIONS = {
    "client_arrives": "a visitor comes to the desk or sits down in the client chair",
    "id_shown": "the visitor shows or hands an ID card, a passport or a phone screen with a document to the cashier",
    "cash_from_client": "the visitor puts cash on the desk or hands it to the cashier",
    "machine_count": "the cashier runs banknotes through the counting machine",
    "manual_count": "the cashier counts banknotes by hand",
    "note_rejected": "the counting machine rejects a banknote",
    "part_separated": "the cashier takes a part of a stack of banknotes",
    "cash_to_client": "the cashier hands cash to the visitor or pushes it across the desk",
    "client_leaves": "the visitor gets up and leaves",
    "cashier_leaves": "the cashier gets up and walks away from the desk or leaves the room",
    "cashier_returns": "the cashier comes back to the desk",
    "safe_opened": "the safe or metal cabinet is opened",
    "door_open": "the door of the room is open",
    "other_person": "another person enters the room, looks in through the door or glass, or comes to the cashier's side",
    "phone": "the cashier holds or uses a smartphone",
    "food_drink": "the cashier eats or drinks",
    "cash_bag": "a sealed cash bag is handed over or put away",
    "personal_items": "the cashier puts a personal bag, clothes or a wallet on the desk",
    "hand_hidden": "the cashier's hand with banknotes goes to a pocket, under clothing or below the desk",
}

TRIGGERS = {
    "cash_from_client": [("no_id_check", -4, 4), ("count_without_client", -2, 8)],
    "cash_to_client": [("no_id_check", -4, 4), ("payout_without_count", -6, 4), ("client_substitution", -6, 4)],
    "machine_count": [("rejected_note_added", -2, 8)],
    "note_rejected": [("rejected_note_added", -2, 8)],
    "manual_count": [("manual_count", -2, 8)],
    "part_separated": [("payout_without_count", -2, 8)],
    "client_leaves": [("count_without_client", -2, 8), ("unattended_valuables", -2, 8)],
    "client_arrives": [("client_substitution", -2, 8), ("unattended_valuables", -2, 6)],
    "cashier_leaves": [("unattended_valuables", 0, 8), ("workstation_unlocked", 0, 8), ("safe_left_open", 0, 8),
                       ("key_left", 0, 8), ("documents_left_open", 0, 8)],
    "safe_opened": [("safe_left_open", 0, 8)],
    "door_open": [("door_left_open", -2, 8)],
    "other_person": [("unauthorized_person", -3, 5)],
    "phone": [("phone_use", -3, 5)],
    "food_drink": [("food_drink", -3, 5)],
    "cash_bag": [("bag_unchecked", -3, 6)],
    "personal_items": [("personal_items", -3, 5)],
    "hand_hidden": [("cash_concealment", -3, 4)],
}

LINE = re.compile(r"t\s*=\s*([\d.]+)\s*s?\s*\|\s*([a-z_]+)\s*(?:\|\s*(.*))?")


async def chat(client: httpx.AsyncClient, content: list[dict], prefill: str, **extra) -> dict:
    payload = {
        "model": config.VLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": content},
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


def timeline_question() -> str:
    names = "\n".join(f"{k}: {v}" for k, v in ACTIONS.items())
    return (f"Which of these events happen in these frames?\n{names}\n"
            "Write one line per event in time order in the form: t=<seconds> | <event> | <a few words>. "
            "Use the t values of the frames. Write each event once, at the frame where it starts, and do not repeat "
            "an ongoing state in later frames. Write only events you clearly see. If none of them happens, write: none")


def parse_timeline(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        m = LINE.search(line)
        if m and m.group(2) in ACTIONS:
            out.append({"t": float(m.group(1).rstrip(".")), "event": m.group(2), "note": (m.group(3) or "").strip()})
    return out


async def timeline_chunk(client: httpx.AsyncClient, chunk: list[Frame]) -> list[dict]:
    async with semaphore():
        choice = await probe.complete(client, probe.frame_content(chunk), timeline_question(), max_tokens=200)
    return parse_timeline(choice["message"]["content"])


async def timeline(client: httpx.AsyncClient, frames: list[Frame]) -> list[dict]:
    step = max(1, round(config.SAMPLE_FPS))
    sparse = frames[::step]
    chunks = [sparse[i:i + TIMELINE_CHUNK] for i in range(0, len(sparse), TIMELINE_CHUNK)]
    parts = await asyncio.gather(*(timeline_chunk(client, c) for c in chunks))
    return sorted((e for p in parts for e in p), key=lambda e: e["t"])


def timeline_text(events: list[dict]) -> str:
    if not events:
        return "no events recorded"
    return "\n".join(f"t={e['t']:g}s {e['event']}" + (f" ({e['note']})" if e["note"] else "") for e in events)


def scan_candidates(scan_dir: Path) -> list[dict]:
    windows = json.loads((scan_dir / "raw_probs.json").read_text())
    located = {(e["rule_id"], e["window_start"]): e["t"] for e in json.loads((scan_dir / "raw_events.json").read_text())}
    out = []
    for w in windows:
        for r, p in w["probs"].items():
            if p >= SCAN_MIN:
                out.append({"rule_id": r, "t": located.get((r, w["start"]), w["start"]), "lo": w["start"] - 1,
                            "hi": w["end"] + 1, "scan_p": p, "source": "scan"})
    return out


def timeline_candidates(events: list[dict], duration: float) -> list[dict]:
    out = []
    for e in events:
        for rule_id, before, after in TRIGGERS.get(e["event"], []):
            lo, hi = e["t"] + before, e["t"] + after
            if rule_id == "no_id_check":
                if any(x["event"] == "id_shown" and x["t"] <= e["t"] + 2 for x in events):
                    continue
                arrivals = [x["t"] for x in events if x["event"] == "client_arrives" and x["t"] <= e["t"]]
                lo = min(lo, (arrivals[-1] if arrivals else 0.0) - 1)
            out.append({"rule_id": rule_id, "t": e["t"], "lo": max(0.0, lo), "hi": min(duration, hi),
                        "scan_p": 0.0, "source": f"timeline:{e['event']}"})
    return out


def merge_candidates(cands: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for c in sorted(cands, key=lambda c: (c["rule_id"], c["lo"])):
        last = merged[-1] if merged else None
        if last and last["rule_id"] == c["rule_id"] and c["lo"] <= last["hi"] and max(last["hi"], c["hi"]) - last["lo"] <= MAX_SPAN_SEC:
            last["hi"] = max(last["hi"], c["hi"])
            if c["scan_p"] > last["scan_p"]:
                last["t"], last["scan_p"] = c["t"], c["scan_p"]
            if c["source"] not in last["source"]:
                last["source"] += "+" + c["source"]
        else:
            merged.append(dict(c))
    merged.sort(key=lambda c: (-c["scan_p"], "timeline" not in c["source"]))
    return merged[:MAX_CANDIDATES]


def verify_content(frames: list[Frame], rule: dict, events: list[dict]) -> list[dict]:
    head = [{"type": "text", "text": "Timeline of the whole recording from a quick first pass (it may miss or confuse events):\n"
             + timeline_text(events)}]
    task = (f"Rule {rule['code']}: violation if {rule['visual']}\nNot a violation: {rule['not_violation']}\n"
            "Look closely at these frames and at the timeline. Describe in one to three sentences what exactly happens "
            "that matters for this rule, including anything that shows it is not a violation.")
    return head + probe.frame_content(frames) + [{"type": "text", "text": task}]


async def verify(client: httpx.AsyncClient, video: Path, out_dir: Path, c: dict, events: list[dict]) -> dict:
    rule = rules.rule(c["rule_id"])
    span = max(c["hi"] - c["lo"], 0.5)
    fps = min(VERIFY_FPS, VERIFY_FRAMES / span)
    d = out_dir / f"{c['rule_id']}_{c['lo']:.1f}"
    frames = (await asyncio.to_thread(sample_segment, video, d, c["lo"], c["hi"], fps, VERIFY_WIDTH))[:VERIFY_FRAMES]
    if not frames:
        return {**c, "p": 0.0, "p_direct": 0.0, "obs": "", "t_verify": c["t"], "frames": 0}
    content = verify_content(frames, rule, events)
    question = f"Is rule {rule['code']} clearly violated in these frames, yes or no?\nAnswer:"
    async with semaphore():
        direct = await chat(client, content, question, max_tokens=1, logprobs=True, top_logprobs=10)
        obs_choice = await chat(client, content, "Observation:", max_tokens=70, stop=["\nVerdict", "\n\n", "\nIs rule"])
        obs = obs_choice["message"]["content"].strip()
        base = f"Observation: {obs}\n"
        yn = await chat(client, content, base + question, max_tokens=1, logprobs=True, top_logprobs=10)
        p = round(probe.p_yes(yn), 4)
        t = c["t"]
        if p >= 0.1:
            n = len(frames)
            when = (base + f"Rule {rule['code']} is violated. In which frame (A-{probe.LETTERS[n - 1]}) does it first "
                    "become clearly visible? Answer with one letter.\nAnswer: Frame")
            lp = probe.top(await chat(client, content, when, max_tokens=1, logprobs=True, top_logprobs=20))
            score = lambda i: max(lp.get(probe.LETTERS[i], -1e9), lp.get(" " + probe.LETTERS[i], -1e9))
            t = frames[max(range(n), key=score)].t
    return {**c, "p": p, "p_direct": round(probe.p_yes(direct), 4), "obs": obs, "t_verify": t, "frames": len(frames)}


async def analyze(video: Path, work_dir: Path, progress=None, deadline: float | None = None,
                  candidate: float | None = None, scan_dir: Path | None = None) -> list[Event]:
    scan_dir = scan_dir or work_dir / "scan"
    duration = (await asyncio.to_thread(video_info, video))["duration"]
    scan_deadline = deadline - VERIFY_RESERVE_SEC if deadline else None

    async with httpx.AsyncClient(timeout=config.VLM_TIMEOUT) as client:
        if not (scan_dir / "raw_probs.json").exists():
            scan_progress = (lambda x: progress(0.7 * x)) if progress else None
            await probe.analyze(video, scan_dir, scan_progress, scan_deadline, candidate)
        frames = [Frame(i, round(i / config.SAMPLE_FPS, 2), p) for i, p in enumerate(sorted((scan_dir / "frames").glob("*.jpg")))]
        events = await timeline(client, frames)
        (work_dir / "timeline.json").write_text(json.dumps(events, ensure_ascii=False, indent=1), encoding="utf-8")

        cands = merge_candidates(scan_candidates(scan_dir) + timeline_candidates(events, duration))
        tasks = [asyncio.create_task(verify(client, video, work_dir / "verify", c, events)) for c in cands]
        timeout = max(1.0, deadline - time.time()) if deadline else None
        finished, pending = (await asyncio.wait(tasks, timeout=timeout)) if tasks else (set(), set())
        for t in pending:
            t.cancel()
        if pending:
            log.warning("deadline reached: %d of %d verifications skipped", len(pending), len(tasks))
        checked = [t.result() for t in tasks if t in finished]
    if progress:
        progress(1.0)

    (work_dir / "candidates.json").write_text(json.dumps(checked, ensure_ascii=False, indent=1), encoding="utf-8")
    (work_dir / "raw_probs.json").write_text(
        json.dumps([{"start": c["lo"], "end": c["hi"], "probs": {c["rule_id"]: c["p"]}} for c in checked], indent=1),
        encoding="utf-8")
    out = [Event(c["rule_id"], c["t_verify"], c["p"], c["obs"], c["lo"], c["hi"]) for c in checked]
    (work_dir / "raw_events.json").write_text(json.dumps([asdict(e) for e in out], ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    return out


async def describe(video_dir: Path, e: Event) -> str:
    return await probe.describe(video_dir / "scan", e)
