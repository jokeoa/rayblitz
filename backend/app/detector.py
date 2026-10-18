import threading
from functools import lru_cache
from statistics import median

from app.video import Frame
from app import config, role_context

MODEL = "PekingU/rtdetr_v2_r50vd"
CLASSES = {"person", "laptop"}
SCORE = 0.5
ZONE_SCALE = 0.75
MIN_LAPTOP_SHARE = 0.3
SMOOTH = 5
LEAVE_BEFORE, LEAVE_AFTER = 2.0, 10.0
LEAVE_RULES = {"workstation_unlocked", "key_left", "documents_left_open"}
OWL_MODEL = "google/owlv2-base-patch16-ensemble"
OBJECT_QUERIES = {"safe": ["a metal cabinet", "a grey metal safe", "a white metal cabinet"]}
OWL_SCORE = 0.15
OWL_FRAMES = 5
_lock = threading.Lock()


@lru_cache
def _model():
    import torch
    from transformers import AutoImageProcessor, AutoModelForObjectDetection

    device = "cuda" if torch.cuda.is_available() else "cpu"
    proc = AutoImageProcessor.from_pretrained(MODEL)
    model = AutoModelForObjectDetection.from_pretrained(MODEL).to(device).eval()
    return proc, model, device


def detect(frames: list[Frame], batch: int = 16) -> list[dict]:
    with _lock:
        return _detect(frames, batch)


def _detect(frames: list[Frame], batch: int) -> list[dict]:
    import torch
    from PIL import Image

    proc, model, device = _model()
    labels = model.config.id2label
    rows = []
    for i in range(0, len(frames), batch):
        chunk = frames[i:i + batch]
        images = [Image.open(f.path).convert("RGB") for f in chunk]
        inputs = proc(images=images, return_tensors="pt").to(device)
        with torch.no_grad():
            out = model(**inputs)
        sizes = torch.tensor([im.size[::-1] for im in images], device=device)
        for f, d in zip(chunk, proc.post_process_object_detection(out, target_sizes=sizes, threshold=SCORE)):
            rows.append({"t": f.t, "objects": [
                {"label": labels[int(l)], "score": round(float(s), 3), "box": [round(float(x), 1) for x in b]}
                for s, l, b in zip(d["scores"], d["labels"], d["boxes"]) if labels[int(l)] in CLASSES]})
    return rows


def max_scores(images: list, label: str, batch: int = 8) -> list[float]:
    import torch

    if not images:
        return []
    with _lock:
        proc, model, device = _model()
        target = next(i for i, name in model.config.id2label.items() if name == label)
        out = []
        for i in range(0, len(images), batch):
            chunk = images[i:i + batch]
            inputs = proc(images=chunk, return_tensors="pt").to(device)
            with torch.no_grad():
                res = model(**inputs)
            sizes = torch.tensor([im.size[::-1] for im in chunk], device=device)
            for d in proc.post_process_object_detection(res, target_sizes=sizes, threshold=0.05):
                out.append(max((float(s) for s, l in zip(d["scores"], d["labels"]) if int(l) == target), default=0.0))
        return out


def laptop_box(rows: list[dict]) -> list[float] | None:
    boxes = [max((o for o in r["objects"] if o["label"] == "laptop"), key=lambda o: o["score"])["box"]
             for r in rows if any(o["label"] == "laptop" for o in r["objects"])]
    if not rows or len(boxes) < MIN_LAPTOP_SHARE * len(rows):
        return None
    return [median(b[i] for b in boxes) for i in range(4)]


def expand(box: list[float], scale: float) -> list[float]:
    x0, y0, x1, y1 = box
    w, h = (x1 - x0) * scale, (y1 - y0) * scale
    return [x0 - w, y0 - h, x1 + w, y1 + h]


def desk_zone(rows: list[dict]) -> list[float] | None:
    box = laptop_box(rows)
    return expand(box, ZONE_SCALE) if box else None


def overlaps(box: list[float], zone: list[float]) -> bool:
    return box[0] < zone[2] and box[2] > zone[0] and box[1] < zone[3] and box[3] > zone[1]


def persons_near(rows: list[dict], t: float, zone: list[float] | None) -> list[list[float]]:
    bankers = role_context.banker_boxes(t, config.FRAME_WIDTH)
    if bankers is not None:
        return [b for b in bankers if zone is None or overlaps(b, zone)]
    if not rows:
        return []
    row = min(rows, key=lambda r: abs(r["t"] - t))
    return [o["box"] for o in row["objects"] if o["label"] == "person" and (zone is None or overlaps(o["box"], zone))]


def smooth(xs: list[int], k: int = SMOOTH) -> list[int]:
    half = k // 2
    out = []
    for i in range(len(xs)):
        w = sorted(xs[max(0, i - half):i + half + 1])
        out.append(w[len(w) // 2])
    return out


def events(rows: list[dict]) -> dict:
    zone = desk_zone(rows)
    people = role_context.current.get()
    if people and people['geometry']['objects']['desk']:
        scale = config.FRAME_WIDTH / people['info']['width']
        zone = [v*scale for v in people['geometry']['objects']['desk']['box']]
    known_roles = role_context.desk_events(rows, zone, config.FRAME_WIDTH)
    if known_roles is not None:
        return known_roles
    if zone is None:
        return {"zone": None, "counts": [], "leaves": [], "arrivals": [], "empty": []}
    raw = [sum(o["label"] == "person" and overlaps(o["box"], zone) for o in r["objects"]) for r in rows]
    counts = smooth(raw)
    ts = [r["t"] for r in rows]
    leaves = [ts[i] for i in range(1, len(counts)) if counts[i] < counts[i - 1]]
    arrivals = [ts[i] for i in range(1, len(counts)) if counts[i] > counts[i - 1]]
    empty, start = [], None
    for t, c in zip(ts, counts):
        if c == 0 and start is None:
            start = t
        if c > 0 and start is not None:
            empty.append([start, t])
            start = None
    if start is not None:
        empty.append([start, ts[-1]])
    return {"zone": zone, "counts": counts, "leaves": leaves, "arrivals": arrivals, "empty": empty}


def gate(ev: dict, start: float, end: float) -> tuple[bool, float | None]:
    if ev["zone"] is None:
        return (False if ev.get('basis') else True), None
    near = [t for t in ev["leaves"] if start <= t + LEAVE_AFTER and end >= t - LEAVE_BEFORE]
    near += [s for s, e in ev["empty"] if s <= end and e >= start]
    return (True, min(near)) if near else (False, None)


@lru_cache
def _owl():
    import torch
    from transformers import Owlv2ForObjectDetection, Owlv2Processor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    return Owlv2Processor.from_pretrained(OWL_MODEL), Owlv2ForObjectDetection.from_pretrained(OWL_MODEL).to(device).eval(), device


def iou(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _owl_candidates(images: list, queries: list[str]) -> list[list[tuple[float, list[float]]]]:
    import torch

    proc, model, device = _owl()
    out = []
    for img in images:
        inputs = proc(text=[queries], images=img, return_tensors="pt").to(device)
        with torch.no_grad():
            res = model(**inputs)
        side = max(img.size)
        d = proc.post_process_grounded_object_detection(res, threshold=0.05, target_sizes=torch.tensor([[side, side]], device=device))[0]
        out.append(sorted(zip(d["scores"].tolist(), d["boxes"].tolist()), reverse=True)[:5])
    return out


def locate(images: list, queries: list[str]) -> list[float] | None:
    with _lock:
        per_frame = _owl_candidates(images, queries)
    best, support = None, 0.0
    for i, cands in enumerate(per_frame):
        for s, b in cands:
            if s < OWL_SCORE:
                continue
            total = s + sum(max((s2 for s2, b2 in other if iou(b, b2) > 0.5), default=0.0)
                            for j, other in enumerate(per_frame) if j != i)
            if total > support:
                best, support = b, total
    return best
