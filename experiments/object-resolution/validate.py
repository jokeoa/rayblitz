"""Verify media identity, model consistency, coordinate mapping and traceable IDs."""
import hashlib
from PIL import Image
from common import ROOT, ARMS, read_json, sha256, write_json

root = ROOT / "runs"
manifest = read_json(root / "manifest.json")
cfg = manifest["config"]
assert sha256(ROOT / "config.json") == manifest["config_sha256"]
assert read_json(root / "status.json")["status"] == "complete"
pixel_hashes = read_json(root / "pixel-hashes.json")
counts = {"frames": 0, "verified_images": 0, "detections": 0, "tracks": 0}
classes = {c["id"] for c in cfg["classes"]}
for ep in manifest["episodes"]:
    vid = ep["video"]
    width, height = ep["size"]
    detections = read_json(root / vid / "detections.json")
    tracks = read_json(root / vid / "tracks.json")
    assert detections["config_sha256"] == manifest["config_sha256"]
    assert detections["source_sha256"] == ep["source_sha256"]
    assert detections["runtime_sha256"] == sha256(root / "runtime.json")
    assert tracks["detections_sha256"] == sha256(root / vid / "detections.json")
    assert len(detections["rows"]) == len(ep["frames"]) == cfg["fps"] * cfg["duration"]
    for i, frame in enumerate(ep["frames"]):
        for key in ("native", "reduced"):
            with Image.open(root / frame[key]) as image:
                assert hashlib.sha256(image.convert("RGB").tobytes()).hexdigest() == pixel_hashes[frame[key]], frame[key]
            counts["verified_images"] += 1
        row = detections["rows"][i]
        assert row["frame"] == i and row["t"] == frame["t"]
        for arm in ARMS:
            assert row["seconds"][arm] > 0
            for p in row["arms"][arm]:
                x0, y0, x1, y1 = p["box"]
                assert 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height
                assert p["class"] in classes and 0 <= p["score"] <= 1
                counts["detections"] += 1
        counts["frames"] += 1
    for fps, arms in tracks["arms"].items():
        expected = list(range(0, len(ep["frames"]), cfg["fps"] // int(fps)))
        for arm, track in arms.items():
            assert [r["frame"] for r in track["rows"]] == expected
            for row in track["rows"]:
                assert len({p["id"] for p in row["tracks"]}) == len(row["tracks"])
                for p in row["tracks"]:
                    source = detections["rows"][row["frame"]]["arms"][arm][p["detection_index"]]
                    assert p["class"] == source["class"] and p["observed_box"] == source["box"]
                    counts["tracks"] += 1
write_json(root / "validation.json", {"status": "passed", "checks": counts,
    "meaning": "Structural/provenance checks only, not object detection or tracking accuracy."})
print(counts)
