"""Audit reuse of the reviewed geometry, equal filtering, and track support."""
from common import ROOT, read_json, sha256, write_json
from desk_scope import in_desk_region

root = ROOT / "runs"
scope = read_json(root / "desk-scope.json")
manifest = read_json(root / "manifest.json")
assert read_json(root / "validation.json")["status"] == "passed"
assert read_json(root / "desk-status.json")["status"] == "complete"
assert scope["manifest_sha256"] == sha256(root / "manifest.json")
counts = {"videos": 0, "frames": 0, "candidates": 0, "tracks": 0}
for ep in manifest["episodes"]:
    video = ep["video"]
    if video not in scope["videos"]:
        assert any(e["video"] == video for e in scope["excluded"])
        continue
    desk = scope["videos"][video]
    baseline = read_json(root / video / "detections.json")
    data = read_json(root / video / "desk-detections.json")
    tracks = read_json(root / video / "desk-tracks.json")
    assert data["baseline_sha256"] == sha256(root / video / "detections.json")
    assert data["scope_sha256"] == sha256(root / "desk-scope.json")
    assert data["source_sha256"] == ep["source_sha256"] == desk["source_sha256"]
    assert data["config_sha256"] == manifest["config_sha256"]
    assert tracks["detections_sha256"] == sha256(root / video / "desk-detections.json")
    assert len(data["rows"]) == len(ep["frames"])
    for name, digest in data["code"].items():
        assert digest == sha256(root / "desk-source" / name)
    for row, original, frame in zip(data["rows"], baseline["rows"], ep["frames"], strict=True):
        assert row["frame"] == frame["frame"] and row["t"] == frame["t"]
        for arm in ("reduced", "native", "tiles"):
            assert row["arms"][arm] == [p for p in original["arms"][arm] if in_desk_region(p, desk)]
        for arm, predictions in row["arms"].items():
            assert row["seconds"][arm] > 0
            for p in predictions:
                assert in_desk_region(p, desk)
                assert 0 <= p["box"][0] < p["box"][2] <= ep["size"][0]
                assert 0 <= p["box"][1] < p["box"][3] <= ep["size"][1]
                assert 0.05 <= p["score"] <= 1
                counts["candidates"] += 1
        counts["frames"] += 1
    for fps, modes in tracks["arms"].items():
        expected = list(range(0, len(ep["frames"]), manifest["config"]["fps"] // int(fps)))
        assert set(modes) == {"reduced", "native", "tiles", "desk"}
        for arm, mode in modes.items():
            assert [row["frame"] for row in mode["rows"]] == expected
            for row in mode["rows"]:
                assert len({p["id"] for p in row["tracks"]}) == len(row["tracks"])
                for p in row["tracks"]:
                    source = data["rows"][row["frame"]]["arms"][arm][p["detection_index"]]
                    assert p["class"] == source["class"] and p["observed_box"] == source["box"]
                    counts["tracks"] += 1
    counts["videos"] += 1
refs = read_json(ROOT / "reference_objects.json")
for ref in refs["objects"]:
    assert in_desk_region(ref, scope["videos"][ref["video"]]), ref
assert not any(o["entity"] in {"safe", "package-in-hand"} for o in refs["objects"])
write_json(root / "desk-validation.json", {"status": "passed", "checks": counts,
    "meaning": "Structural/provenance checks, not proof of physical contact or detection/tracking accuracy."})
print(counts)
