import asyncio
import io
from pathlib import Path

import httpx
from PIL import Image

from app import config, detector
from app.analyzers import probe
from app.analyzers.common import semaphore
from app.video import b64, frame_jpeg

QUESTIONS = {
    "screen": ("This is a zoomed crop of the laptop on a bank cashier's desk. Does the laptop screen show an open "
               "working application window: a bright window with text, tables or forms? A lock screen (a picture or "
               "dark background with a clock), a dark screen or a closed lid is not a working window. "
               "Answer yes or no.\nAnswer:"),
    "desk": ("This is a zoomed crop of a bank cashier's desk. Are paper documents, document folders, ID copies or "
             "rubber stamps lying openly on the desk? Answer yes or no.\nAnswer:"),
    "safe": ("This is a zoomed crop of a grey metal safe or cabinet in a bank cash room. Is its door open? "
             "Answer yes or no.\nAnswer:"),
    "phone": ("This is a zoomed crop of one person in a bank cash room. Is this person looking at or typing on the screen "
              "of a smartphone held in the hand? Banknotes, a card, papers or a desk phone do not count. "
              "Answer yes or no.\nAnswer:"),
    "food": ("This is a zoomed crop of one person in a bank cash room. Is this person eating, or drinking from a cup or "
             "bottle held to the mouth? Handling banknotes or papers does not count. Answer yes or no.\nAnswer:"),
    "cash": ("This is a zoomed crop of one person in a bank cash room. Is this person putting banknotes into a pocket, "
             "under clothing or into a personal bag? Answer yes or no.\nAnswer:"),
}
MARGINS = {"screen": 0.5, "desk": 1.5, "safe": 0.2, "phone": 0.1, "food": 0.1, "cash": 0.1}
HANDS = {"phone_use": "phone_det", "food_drink": "food", "cash_concealment": "cash"}
DETECTED = {"phone_det": "cell phone"}
DET_CROP = 640
DET_MARGIN = 0.15
COMPOSITE = {"workstation_unlocked": "screen", "documents_left_open": "desk", "safe_left_open": "safe", **HANDS}
DESK_KEYS = {"screen", "desk"}
CROP_SIZE = 448
OFFSETS = (1.0, 3.0, 5.0)
MAX_TIMES = 12
SAFE_STEP = 3.0
SUSTAIN = 3


def times(ev: dict, duration: float) -> list[float]:
    starts = [s for s, _ in ev["empty"]]
    ts = sorted({round(t + o, 1) for t in starts for o in OFFSETS if t + o < duration - 0.1})
    return ts[:MAX_TIMES]


def periodic(duration: float) -> list[float]:
    ts, t = [], 1.0
    while t < duration - 0.1:
        ts.append(round(t, 1))
        t += SAFE_STEP
    return ts


def crop_image(img: Image.Image, box: list[float], scale: float, size: int) -> Image.Image:
    x0, y0, x1, y1 = (max(0.0, v) for v in box)
    c = img.crop((x0 * scale, y0 * scale, min(img.width, x1 * scale), min(img.height, y1 * scale)))
    k = size / max(c.width, c.height)
    return c.resize((max(1, round(c.width * k)), max(1, round(c.height * k))), Image.LANCZOS)


def crop(img: Image.Image, box: list[float], scale: float) -> bytes:
    buf = io.BytesIO()
    crop_image(img, box, scale, CROP_SIZE).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def detector_facts(video: Path, rows: list[dict], ev: dict, hand: list[tuple[str, float]]) -> list[dict]:
    out = []
    for key, t in hand:
        img = Image.open(io.BytesIO(frame_jpeg(video, t))).convert("RGB")
        scale = img.width / config.FRAME_WIDTH
        crops = [crop_image(img, detector.expand(b, DET_MARGIN), scale, DET_CROP)
                 for b in detector.persons_near(rows, t, ev["zone"])]
        out += [{"t": t, key: round(p, 4)} for p in detector.max_scores(crops, DETECTED[key])]
    return out


async def ask(client: httpx.AsyncClient, image: bytes, question: str) -> float:
    content = [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64(image)}}]
    async with semaphore():
        choice = await probe.complete(client, content, question, max_tokens=1, logprobs=True, top_logprobs=10)
    return round(probe.p_yes(choice), 4)


async def sample(client: httpx.AsyncClient, video: Path, t: float, boxes: dict[str, list[float]]) -> dict:
    img = Image.open(io.BytesIO(await asyncio.to_thread(frame_jpeg, video, t))).convert("RGB")
    scale = img.width / config.FRAME_WIDTH
    keys = list(boxes)
    ps = await asyncio.gather(*(ask(client, crop(img, detector.expand(boxes[k], MARGINS[k]), scale), QUESTIONS[k])
                                for k in keys))
    return {"t": t, **dict(zip(keys, ps))}


def native_frames(video: Path, duration: float, n: int) -> list[Image.Image]:
    return [Image.open(io.BytesIO(frame_jpeg(video, duration * (i + 0.5) / n))).convert("RGB") for i in range(n)]


def window_times(start: float, end: float) -> list[float]:
    return sorted({round(start, 1), round((start + end) / 2, 1), round(end, 1)})


async def facts(video: Path, rows: list[dict], ev: dict, duration: float, rule_ids: list[str] | None = None,
                windows: list[tuple[str, float, float]] | None = None) -> list[dict]:
    keys = {COMPOSITE[r] for r in rule_ids} if rule_ids is not None else set(QUESTIONS)
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=config.VLM_TIMEOUT) as client:
        laptop = detector.laptop_box(rows)
        desk_keys = sorted(keys & DESK_KEYS)
        if laptop and desk_keys:
            out += await asyncio.gather(*(sample(client, video, t, {k: laptop for k in desk_keys})
                                          for t in times(ev, duration)))
        if "safe" in keys:
            images = await asyncio.to_thread(native_frames, video, duration, detector.OWL_FRAMES)
            box = await asyncio.to_thread(detector.locate, images, detector.OBJECT_QUERIES["safe"])
            if box:
                safe = [v * config.FRAME_WIDTH / images[0].width for v in box]
                out += await asyncio.gather(*(sample(client, video, t, {"safe": safe}) for t in periodic(duration)))
        hand = [(HANDS[r], t) for r, start, end in windows or [] if HANDS.get(r) in keys for t in window_times(start, end)]
        out += await asyncio.gather(*(sample(client, video, t, {key: box}) for key, t in hand if key in QUESTIONS
                                      for box in detector.persons_near(rows, t, ev["zone"])))
        out += await asyncio.to_thread(detector_facts, video, rows, ev, [(k, t) for k, t in hand if k in DETECTED])
    return out


def empty_start(ev: dict, t: float) -> float:
    return max((s for s, _ in ev["empty"] if s <= t), default=t)


def sustained(samples: list[dict], key: str) -> tuple[float, float]:
    s = sorted(samples, key=lambda x: x["t"])
    n = min(SUSTAIN, len(s))
    i = max(range(len(s) - n + 1), key=lambda i: min(x[key] for x in s[i:i + n]))
    return min(x[key] for x in s[i:i + n]), s[i]["t"]


def composite(samples: list[dict], ev: dict) -> dict[str, tuple[float, float]]:
    out = {}
    for rule_id, key in COMPOSITE.items():
        s = [x for x in samples if key in x]
        if not s:
            continue
        if key == "safe":
            out[rule_id] = sustained(s, key)
        elif key not in DESK_KEYS:
            best = max(s, key=lambda x: x[key])
            out[rule_id] = (best[key], best["t"])
        else:
            best = max(s, key=lambda x: x[key])
            out[rule_id] = (best[key], empty_start(ev, best["t"]))
    return out
