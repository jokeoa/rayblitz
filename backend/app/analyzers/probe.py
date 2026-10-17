import asyncio
import json
import logging
import math
import string
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from app import config, rules
from app.analyzers.common import SYSTEM, Event, semaphore, windows
from app.video import Frame, b64, sample_frames

log = logging.getLogger("probe")

LETTERS = string.ascii_uppercase
YES = {"yes", "Yes", " yes", " Yes", "YES"}
NO = {"no", "No", " no", " No", "NO"}
TASK = "Check these frames against the bank cash room rules."
PRIME = {"catalog": "I will check only rule", "single": "I will check these frames against one rule.\n"}


def frame_content(chunk: list[Frame]) -> list[dict]:
    content = [{"type": "text", "text": "Frames from the ceiling camera in time order:"}]
    for i, f in enumerate(chunk):
        content.append({"type": "text", "text": f"Frame {LETTERS[i]} (t={f.t:.1f}s):"})
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64(f.path.read_bytes())}})
    return content


async def complete(client: httpx.AsyncClient, content: list[dict], question: str, **extra) -> dict:
    payload = {
        "model": config.VLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": content + [{"type": "text", "text": question}]},
        ],
        "temperature": 0,
        **config.VLM_EXTRA_BODY,
        **extra,
    }
    r = await client.post(f"{config.VLM_BASE_URL}/chat/completions", json=payload)
    r.raise_for_status()
    return r.json()["choices"][0]


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


async def prime(client: httpx.AsyncClient, content: list[dict]) -> None:
    await ask(client, content, PRIME[config.PROMPT_FORMAT], max_tokens=1)


def user_text() -> str:
    if config.PROMPT_FORMAT == "catalog":
        block = "\n".join(f"Rule {r['code']}: violation if {r['visual']} Not a violation: {r['not_violation']}" for r in rules.rules())
        return f"Rules:\n{block}\nI will ask about one rule at a time."
    return TASK


def top(choice: dict) -> dict[str, float]:
    return {t["token"]: t["logprob"] for t in choice["logprobs"]["content"][0]["top_logprobs"]}


def p_yes(choice: dict) -> float:
    lp = top(choice)
    y = sum(math.exp(v) for k, v in lp.items() if k in YES)
    n = sum(math.exp(v) for k, v in lp.items() if k in NO)
    return y / (y + n) if y + n else 0.0


def scores(probs: dict[str, float], norm: str | None = None) -> dict[str, float]:
    if (norm or config.SCORE_NORM) != "window" or not probs:
        return dict(probs)
    mean = sum(probs.values()) / len(probs)
    return {r: round(p - mean, 4) for r, p in probs.items()}


def yes_no_question(rule: dict) -> str:
    if config.PROMPT_FORMAT == "catalog":
        return (f"{PRIME['catalog']} {rule['code']} against these frames.\n"
                f"Is rule {rule['code']} clearly violated in these frames, yes or no?\nAnswer:")
    return (f"{PRIME['single']}Rule: {rule['visual']}\nExceptions: {rule['not_violation']}\n"
            "Question: is this rule clearly broken in these frames, yes or no?\nAnswer:")


def when_question(rule: dict, n: int) -> str:
    ask_frame = f"In which frame (A-{LETTERS[n - 1]}) does it first become clearly visible? Answer with one letter.\nAnswer: Frame"
    if config.PROMPT_FORMAT == "catalog":
        return f"{PRIME['catalog']} {rule['code']} against these frames.\nRule {rule['code']} is violated. {ask_frame}"
    return f"{PRIME['single']}Rule: {rule['visual']}\nThis rule is broken. {ask_frame}"


def rule_text(rule: dict) -> str:
    return f"Violation: {rule['visual']}\nNot a violation: {rule['not_violation']}\n"


async def first_frame(client: httpx.AsyncClient, content: list[dict], chunk: list[Frame], rule: dict) -> Frame:
    choice = await ask(client, content, when_question(rule, len(chunk)), max_tokens=1, logprobs=True, top_logprobs=20)
    lp = top(choice)
    score = lambda i: max(lp.get(LETTERS[i], -1e9), lp.get(" " + LETTERS[i], -1e9))
    return chunk[max(range(len(chunk)), key=score)]


async def scan_window(client: httpx.AsyncClient, chunk: list[Frame], candidate: float) -> tuple[list[Event], dict]:
    content = frame_content(chunk)
    events = []
    probs = {}
    async with semaphore():
        await prime(client, content)
        for rule in rules.rules():
            choice = await ask(client, content, yes_no_question(rule), max_tokens=1, logprobs=True, top_logprobs=10)
            probs[rule["id"]] = round(p_yes(choice), 4)
        for rule_id, s in scores(probs).items():
            if s >= candidate:
                f = await first_frame(client, content, chunk, rules.rule(rule_id))
                events.append(Event(rule_id, f.t, s, "", chunk[0].t, chunk[-1].t))
    return events, {"start": chunk[0].t, "end": chunk[-1].t, "probs": probs}


async def describe(video_dir: Path, e: Event) -> str:
    frames = sorted((video_dir / "frames").glob("*.jpg"))
    lo, hi = e.t - 2.0, e.t + 2.0
    chunk = [Frame(i, round(i / config.SAMPLE_FPS, 2), p) for i, p in enumerate(frames)]
    chunk = [f for f in chunk if lo <= f.t <= hi][:10]
    rule = rules.rule(e.rule_id)
    question = (
        rule_text(rule)
        + "In one or two short sentences in Russian, describe only the visible actions in these frames that relate to this rule. "
        "Do not draw conclusions, do not mention the rule, do not guess about anything you cannot see."
    )
    async with httpx.AsyncClient(timeout=config.VLM_TIMEOUT) as client, semaphore():
        choice = await complete(client, frame_content(chunk), question, max_tokens=120)
    return choice["message"]["content"].strip()


async def analyze(video: Path, work_dir: Path, progress=None, deadline: float | None = None,
                  candidate: float | None = None) -> list[Event]:
    candidate = config.CANDIDATE if candidate is None else candidate
    frames = await asyncio.to_thread(sample_frames, video, work_dir / "frames", config.SAMPLE_FPS, config.FRAME_WIDTH)
    chunks = windows(frames, config.SAMPLE_FPS, config.WINDOW_SEC, config.STRIDE_SEC)
    done = 0
    own = asyncio.Semaphore(config.VLM_CONCURRENCY)

    async with httpx.AsyncClient(timeout=config.VLM_TIMEOUT) as client:
        async def run(chunk):
            nonlocal done
            async with own:
                res = await scan_window(client, chunk, candidate)
            done += 1
            if progress:
                progress(done / len(chunks))
            return res

        tasks = [None] * len(chunks)
        for i in sorted(range(len(chunks)), key=lambda i: (i % 2, i)):
            tasks[i] = asyncio.create_task(run(chunks[i]))
        timeout = max(1.0, deadline - time.time()) if deadline else None
        finished, pending = await asyncio.wait(tasks, timeout=timeout)
        for t in pending:
            t.cancel()
        if pending:
            log.warning("deadline reached: %d of %d windows skipped", len(pending), len(chunks))
        results = [t.result() for t in tasks if t in finished]

    events = [e for r, _ in results for e in r]
    (work_dir / "raw_probs.json").write_text(json.dumps([w for _, w in results], indent=1), encoding="utf-8")
    (work_dir / "raw_events.json").write_text(
        json.dumps([asdict(e) for e in events], ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return events
