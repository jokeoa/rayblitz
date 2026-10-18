"""Replay cached automatic observations; human annotations are not inputs."""
import argparse
import time
from pathlib import Path

from anchored_role_policy import anchored_role_timeline
from common import ROOT, config, read_json, sha256, write_json
from render import NAMES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos", nargs="+", required=True)
    parser.add_argument("--tracks-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "runs/static-roles")
    args = parser.parse_args()
    args.tracks_root = args.tracks_root.resolve()
    args.output_root = args.output_root.resolve()
    cfg = {**config(), **{k: v for k, v in read_json(ROOT / "reflection_config.json").items()
                         if k in ("min_step_iou", "max_normalized_step", "max_interval_seconds")}}
    for video in args.videos:
        source = ROOT / "runs" / video
        tracks_dir = args.tracks_root / video
        role_path = source / "role_observations.json"
        reflection_path = tracks_dir / "observations.json"
        role_data, reflection_data = read_json(role_path), read_json(reflection_path)
        original_hash = sha256(source / "detections.json")
        if role_data["detections_sha256"] != original_hash or reflection_data["detections_sha256"] != original_hash:
            raise ValueError(f"Observations do not match source detections: {video}")
        if read_json(source / "detections.json")["source_sha256"] != sha256(ROOT / "data" / f"{video}.mov"):
            raise ValueError(f"Source video changed: {video}")
        for name in NAMES:
            track_path = tracks_dir / f"{name}.json"
            tracks = read_json(track_path)
            if tracks["detections_sha256"] != sha256(tracks_dir / "detections.json"):
                raise ValueError(f"Tracker cache changed: {video}/{name}")
            started = time.perf_counter()
            before = read_json(args.output_root / "before" / video / f"{name}.json")
            expected_inputs = {str(p.relative_to(ROOT)): sha256(p) for p in [role_path, reflection_path, track_path, tracks_dir / "detections.json"]}
            if before["inputs"] != expected_inputs or before["config"] != cfg:
                raise ValueError(f"Before/after inputs differ: {video}/{name}")
            anchored, diagnostics = anchored_role_timeline(tracks["rows"], role_data["observations"], reflection_data["observations"], cfg)
            provenance = {"video": video, "tracker": name, "config": cfg,
                          "source_sha256": read_json(source / "detections.json")["source_sha256"],
                          "inputs": expected_inputs,
                          "code_sha256": {p: sha256(ROOT / p) for p in ["anchored_role_policy.py", "person_association.py"]},
                          "human_labels_used_for_inference": False,
                          "comparison": "identical existing reflection-filtered tracks and model observations; role policy only",
                          "causality": "roles use the whole clip; association replay is causal; upstream reflection filtering is offline",
                          "replay_seconds": time.perf_counter() - started}
            out = args.output_root / video
            write_json(out / f"{name}.json", {**provenance, "policy": "immutable_person_roles", **diagnostics, "rows": anchored})
            print(video, name, "banker", diagnostics["opening_banker_person_id"],
                  "people", {p: v["role"] for p, v in diagnostics["people"].items()}, flush=True)


if __name__ == "__main__":
    main()
