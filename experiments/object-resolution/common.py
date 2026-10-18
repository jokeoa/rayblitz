"""Geometry and provenance for a controlled object-resolution experiment."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARMS = ("reduced", "native", "tiles")


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temporary.replace(path)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tiles(width, height, size, overlap):
    """Evenly distribute tiles, with no redundant near-identical final tile."""
    def starts(length):
        if length <= size:
            return [0]
        count = math.ceil((length - size) / (size * (1 - overlap))) + 1
        return [round(i * (length - size) / (count - 1)) for i in range(count)]
    return [(x, y, min(x + size, width), min(y + size, height))
            for y in starts(height) for x in starts(width)]


def original_box(box, crop, image_size):
    """Map the processor's input-image coordinates into native-frame pixels."""
    x0, y0, x1, y1 = crop
    iw, ih = image_size
    b = [x0 + box[0] * (x1 - x0) / iw,
         y0 + box[1] * (y1 - y0) / ih,
         x0 + box[2] * (x1 - x0) / iw,
         y0 + box[3] * (y1 - y0) / ih]
    return [max(x0, min(x1, b[0])), max(y0, min(y1, b[1])),
            max(x0, min(x1, b[2])), max(y0, min(y1, b[3]))]


def iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0


def greedy_matches(predictions, ground_truth, threshold=0.5):
    """Score-ordered, class-specific one-to-one matching (not an AP metric)."""
    used, matched = set(), []
    for pi in sorted(range(len(predictions)), key=lambda i: predictions[i]["score"], reverse=True):
        p = predictions[pi]
        candidates = [(iou(p["box"], g["box"]), gi) for gi, g in enumerate(ground_truth)
                      if gi not in used and p["class"] == g["class"]]
        overlap, gi = max(candidates, default=(0, -1))
        if overlap >= threshold:
            used.add(gi)
            matched.append((pi, gi))
    return matched
