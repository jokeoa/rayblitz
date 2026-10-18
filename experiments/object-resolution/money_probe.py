"""Frozen prompt/crop development comparison; never reads human labels."""
import copy
import time

from PIL import Image

from common import ROOT, iou, read_json, sha256, write_json
from desk_scope import in_desk_region
from owl import Detector

PHRASES = {
    "cash": ["a bundle of paper banknotes", "a stack of banknotes with a paper band",
             "a stack of paper money", "cash banknotes"],
    "packaging": ["an empty paper wrapper from a bundle of banknotes", "a folded paper banknote strap"],
    "cash_counter": ["a banknote counting machine", "a desktop cash counting machine"],
}
FAMILY = {"cash", "card", "document", "packaging"}


def closeups(predictions, width, height):
    candidates = sorted([p for p in predictions if p["class"] in FAMILY and p["score"] >= .10
                         and max(p["box"][2]-p["box"][0], p["box"][3]-p["box"][1]) <= 96],
                        key=lambda p: p["score"], reverse=True)
    kept = []
    for p in candidates:
        if not any(iou(p["box"], q["box"]) >= .7 for q in kept):
            kept.append(p)
    crops = []
    for p in kept:
        x0, y0, x1, y1 = p["box"]
        side = min(160, max(96, 2*max(x1-x0, y1-y0)))
        cx, cy = (x0+x1)/2, (y0+y1)/2
        box = [max(0, round(cx-side/2)), max(0, round(cy-side/2)),
               min(width, round(cx+side/2)), min(height, round(cy+side/2))]
        if box not in crops:
            crops.append(box)
    return crops


def semantic_winners(predictions):
    """Resolve competing money/card/wrapper proposals by model score, not labels."""
    kept = []
    for p in sorted(predictions, key=lambda p: p["score"], reverse=True):
        if p["class"] in FAMILY and any(q["class"] in FAMILY and iou(p["box"], q["box"]) >= .5 for q in kept):
            continue
        kept.append(p)
    return kept


def main():
    root = ROOT / "runs"
    out = root / "money-probe"
    out.mkdir(exist_ok=False)
    manifest, scope = read_json(root/"manifest.json"), read_json(root/"desk-scope.json")
    config = copy.deepcopy(manifest["config"])
    queries, mapping = [], {}
    for cls in config["classes"]:
        for i, phrase in enumerate(PHRASES.get(cls["id"], [cls["prompt"]])):
            query = f'{cls["id"]}__{i}'
            queries.append({**cls, "id": query, "prompt": phrase})
            mapping[query] = cls["id"]
    config["classes"] = queries
    metadata = {"config": config, "query_to_class": mapping, "frames": [0, 10, 20, 30],
                "manifest_sha256": sha256(root/"manifest.json"), "scope_sha256": sha256(root/"desk-scope.json"),
                "selection": "same fixed timestamps in every eligible episode; close-ups from model proposals only",
                "note": "Development comparison after inspecting baseline failures. Not an independent test set. No human labels in inference.",
                "code": {name: sha256(ROOT/name) for name in ("money_probe.py", "owl.py", "common.py", "desk_scope.py")}}
    write_json(out/"metadata.json", metadata)
    for name in metadata["code"]:
        (out/name).write_bytes((ROOT/name).read_bytes())
    write_json(out/"status.json", {"status": "running"})
    detector = Detector(config)
    indices = {c["id"]: i for i, c in enumerate(manifest["config"]["classes"])}
    def convert(predictions):
        for p in predictions:
            p["query"] = p["class"]
            p["class"] = mapping[p["query"]]
            p["class_index"] = indices[p["class"]]
        return semantic_winners(detector.merge(predictions))
    started = time.perf_counter()
    for ep in manifest["episodes"]:
        vid = ep["video"]
        if vid not in scope["videos"]:
            continue
        desk = scope["videos"][vid]
        base = read_json(root/vid/"desk-detections.json")
        rows = []
        first = Image.open(root/ep["frames"][0]["native"]).convert("RGB")
        detector.predict([first.crop(desk["crop"])], [desk["crop"]])
        for frame_index in metadata["frames"]:
            frame = ep["frames"][frame_index]
            path = root/frame["native"]
            if sha256(path) != frame["native_sha256"]:
                raise ValueError("Inference frame changed")
            image = Image.open(path).convert("RGB")
            raw, seconds = detector.predict([image.crop(desk["crop"])], [desk["crop"]])
            full = [p for p in convert(raw) if in_desk_region(p, desk)]
            boxes = closeups(base["rows"][frame_index]["arms"]["desk"], *ep["size"])
            sliced, crop_seconds = detector.predict([image.crop(b) for b in boxes], boxes) if boxes else ([], 0.)
            combined = [p for p in convert(sliced) if in_desk_region(p, desk)]
            # One score-ranked winner per competing family region across both scales.
            combined = semantic_winners(detector.merge(full + combined))
            rows.append({"frame": frame_index, "t": frame["t"], "crop_boxes": boxes,
                         "arms": {"prompt_desk": full, "prompt_closeups": combined},
                         "seconds": {"prompt_desk": seconds, "prompt_closeups": seconds+crop_seconds}})
        write_json(out/f"{vid}.json", {"source_sha256": ep["source_sha256"],
                                      "baseline_sha256": sha256(root/vid/"desk-detections.json"), "rows": rows})
        print(vid, "probe complete", flush=True)
    write_json(out/"status.json", {"status": "complete", "seconds": time.perf_counter()-started})


if __name__ == "__main__":
    main()
