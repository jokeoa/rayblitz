"""A native desk close-up, plus identical desk gates on cached baseline arms."""
import json
from PIL import Image

from common import ROOT, read_json, sha256, write_json
from desk_scope import in_desk_region
from owl import Detector


def main():
    root = ROOT / "runs"
    manifest, scope = read_json(root / "manifest.json"), read_json(root / "desk-scope.json")
    if scope["manifest_sha256"] != sha256(root / "manifest.json"):
        raise ValueError("Desk scope belongs to a different source manifest")
    model = Detector(manifest["config"])
    runtime = read_json(root / "runtime.json")
    processor_metadata = json.loads(json.dumps(model.processor.image_processor.to_dict()))
    if processor_metadata != runtime["processor"] or str(model.model.dtype) != runtime["dtype"]:
        raise ValueError("Desk arm must use the same processor and precision")
    snapshot = root / "desk-source"
    snapshot.mkdir(exist_ok=True)
    for name in ("desk_detect.py", "desk_scope.py", "owl.py", "track.py", "common.py"):
        (snapshot / name).write_bytes((ROOT / name).read_bytes())
    for ep in manifest["episodes"]:
        vid = ep["video"]
        if vid not in scope["videos"]:
            continue
        target = root / vid / "desk-detections.json"
        if target.exists():
            raise ValueError(f"Refusing to overwrite {target}")
        desk = scope["videos"][vid]
        crop = desk["crop"]
        first = Image.open(root / ep["frames"][0]["native"]).convert("RGB").crop(crop)
        model.predict([first], [crop])
        source = read_json(root / vid / "detections.json")
        if source["source_sha256"] != ep["source_sha256"] or source["config_sha256"] != manifest["config_sha256"]:
            raise ValueError("Cached detections do not match source or configuration")
        rows = []
        for frame, baseline in zip(ep["frames"], source["rows"], strict=True):
            path = root / frame["native"]
            if sha256(path) != frame["native_sha256"]:
                raise ValueError("Source frame changed")
            image = Image.open(path).convert("RGB").crop(crop)
            raw, seconds = model.predict([image], [crop])
            arms = {name: [p for p in predictions if in_desk_region(p, desk)] for name, predictions in baseline["arms"].items()}
            arms["desk"] = [p for p in model.merge(raw) if in_desk_region(p, desk)]
            rows.append({"frame": frame["frame"], "t": frame["t"], "arms": arms,
                         "seconds": {**baseline["seconds"], "desk": seconds}})
        write_json(target, {"source_sha256": ep["source_sha256"], "config_sha256": manifest["config_sha256"],
                            "baseline_sha256": sha256(root / vid / "detections.json"),
                            "scope_sha256": sha256(root / "desk-scope.json"), "rows": rows,
                            "code": {p.name: sha256(p) for p in snapshot.glob("*.py")}})
        print(vid, "desk complete", flush=True)


if __name__ == "__main__":
    main()
