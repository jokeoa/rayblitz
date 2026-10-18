"""Class-separated ByteTrack; identical parameters for all resolution arms."""
import argparse
import importlib.metadata
import time

import cv2
import numpy as np
from boxmot import ByteTrack

from common import ROOT, ARMS, read_json, sha256, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--desk", action="store_true", help="Track only cached desk-region proposals")
    args = parser.parse_args()
    root = ROOT / "runs"
    manifest = read_json(root / "manifest.json")
    scope = read_json(root / "desk-scope.json") if args.desk else None
    arms = (*ARMS, "desk") if args.desk else ARMS
    cfg = manifest["config"]
    for ep in manifest["episodes"]:
        vid = ep["video"]
        if args.desk and vid not in scope["videos"]:
            continue
        path = root / vid / ("desk-detections.json" if args.desk else "detections.json")
        detections = read_json(path)
        if detections["config_sha256"] != manifest["config_sha256"]:
            raise ValueError("Incompatible cached detections")
        data = {"detections_sha256": sha256(path), "config_sha256": manifest["config_sha256"],
                "boxmot": importlib.metadata.version("boxmot"), "arms": {},
                "note": "IDs are predictions, local to video/arm/fps/class. Only detector-supported active tracks are exported. Fragment counts and coverage are not tracking accuracy. The 2 fps comparison subsamples the same cached detections."}
        for fps in (cfg["fps"], 2):
            stride = cfg["fps"] // fps
            data["arms"][str(fps)] = {}
            for arm in arms:
                trackers = {c["id"]: ByteTrack(min_conf=cfg["candidate_score"],
                            track_thresh=cfg["track_high_score"], match_thresh=.8,
                            track_buffer=round(cfg["track_lost_seconds"] * 30), frame_rate=fps)
                            for c in cfg["classes"]}
                rows = []
                tick = time.perf_counter()
                for row in detections["rows"][::stride]:
                    image = cv2.imread(str(root / ep["frames"][row["frame"]]["native"]))
                    current = []
                    for cls, tracker in trackers.items():
                        indexed = [(i, p) for i, p in enumerate(row["arms"][arm]) if p["class"] == cls]
                        dets = np.asarray([p["box"] + [p["score"], 0] for _, p in indexed], dtype=np.float32).reshape(-1, 6)
                        tracked = tracker.update(dets, image)
                        for r in tracked:
                            index = int(r[7])
                            source_index, source = indexed[index]
                            current.append({"id": f"{cls}-{int(r[4])}", "class": cls, "box": r[:4].tolist(),
                                            "score": float(r[5]), "detection_index": source_index,
                                            "observed_box": source["box"]})
                    rows.append({"frame": row["frame"], "t": row["t"], "tracks": current})
                data["arms"][str(fps)][arm] = {"rows": rows, "seconds": time.perf_counter() - tick,
                    "max_lost_frames": next(iter(trackers.values())).max_time_lost,
                    "track_count": len({p["id"] for row in rows for p in row["tracks"]})}
        write_json(root / vid / ("desk-tracks.json" if args.desk else "tracks.json"), data)
        print(vid, "tracking complete", flush=True)


if __name__ == "__main__":
    main()
