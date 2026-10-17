import asyncio
from dataclasses import dataclass

from app import config
from app.video import Frame

SYSTEM = (
    "You audit ceiling-camera footage of a bank cash room. The cashier works at a desk with a laptop, "
    "a banknote counter and a safe or metal cabinet. Clients sit across the desk from the cashier. "
    "Report only actions that are clearly visible in the frames. Do not guess about anything you cannot see."
)


@dataclass
class Event:
    rule_id: str
    t: float
    confidence: float
    observation: str
    window_start: float
    window_end: float


_sem: asyncio.Semaphore | None = None


def semaphore() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(config.VLM_CONCURRENCY)
    return _sem


def windows(frames: list[Frame], fps: float, window_sec: float, stride_sec: float) -> list[list[Frame]]:
    size = max(1, round(window_sec * fps))
    step = max(1, round(stride_sec * fps))
    out = []
    start = 0
    while start < len(frames):
        out.append(frames[start:start + size])
        if start + size >= len(frames):
            break
        start += step
    return out
