"""Identical frozen OWLv2 across reduced, native and native-plus-tiles arms."""
import argparse
import importlib.metadata
import platform
import time

import torch
from PIL import Image

from common import ROOT, read_json, sha256, tiles, write_json
from owl import Detector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos", nargs="+")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch", type=int, default=2)
    args = parser.parse_args()
    out = ROOT / "runs"
    manifest = read_json(out / "manifest.json")
    cfg = manifest["config"]
    if sha256(ROOT / "config.json") != manifest["config_sha256"]:
        raise ValueError("Configuration changed after frame preparation")
    start = time.perf_counter()
    detector = Detector(cfg, args.batch)
    processor, model = detector.processor, detector.model
    predict, merge = detector.predict, detector.merge
    torch.cuda.synchronize()
    metadata = {"config_sha256": manifest["config_sha256"], "manifest_sha256": sha256(out / "manifest.json"),
                "model": cfg["model"], "revision": cfg["revision"], "dtype": str(model.dtype),
                "gpu": torch.cuda.get_device_name(0), "python": platform.python_version(),
                "packages": {p: importlib.metadata.version(p) for p in ("torch", "transformers", "torchvision", "boxmot")},
                "processor": processor.image_processor.to_dict(), "batch_size": args.batch,
                "model_load_seconds": time.perf_counter() - start,
                "code": {p.name: sha256(p) for p in ROOT.glob("*.py")},
                "timing_note": "Warm per-frame processor/model/postprocess times; native full-frame predictions are reused in the tiles arm. Tile total includes that native cost. Decode excluded; GPU may be shared."}
    write_json(out / "runtime.json", metadata)

    for episode in manifest["episodes"]:
        vid = episode["video"]
        if args.videos and vid not in args.videos:
            continue
        target = out / vid / ("pilot.json" if args.limit else "detections.json")
        if target.exists():
            raise ValueError(f"Refusing to overwrite {target}")
        width, height = episode["size"]
        whole = (0, 0, width, height)
        crop_boxes = tiles(width, height, cfg["tile_size"], cfg["tile_overlap"])
        # Warm every tensor shape before collecting timings.
        first = Image.open(out / episode["frames"][0]["native"]).convert("RGB")
        predict([first], [whole])
        predict([first.crop(crop_boxes[0])] * args.batch, [crop_boxes[0]] * args.batch)
        rows = []
        wall = time.perf_counter()
        for frame in episode["frames"][:args.limit]:
            for key in ("native", "reduced"):
                if sha256(out / frame[key]) != frame[key + "_sha256"]:
                    raise ValueError("Frame changed")
            native = Image.open(out / frame["native"]).convert("RGB")
            reduced = Image.open(out / frame["reduced"]).convert("RGB")
            low, low_time = predict([reduced], [whole])
            full, full_time = predict([native], [whole])
            sliced, slice_time = predict([native.crop(b) for b in crop_boxes], crop_boxes)
            arms = {"reduced": merge(low), "native": merge(full), "tiles": merge(full + sliced)}
            rows.append({"frame": frame["frame"], "t": frame["t"], "arms": arms,
                         "seconds": {"reduced": low_time, "native": full_time, "tiles": full_time + slice_time},
                         "raw_tiles": sliced})
            if len(rows) % 10 == 0:
                print(vid, len(rows), "frames", round(time.perf_counter() - wall, 1), "seconds", flush=True)
        write_json(target, {"source_sha256": episode["source_sha256"], "config_sha256": manifest["config_sha256"],
                            "runtime_sha256": sha256(out / "runtime.json"), "crop_boxes": crop_boxes,
                            "native_predictions_reused_in_tiles": True, "rows": rows,
                            "processing_wall_seconds": time.perf_counter() - wall})
        print(vid, "saved", target.name, flush=True)


if __name__ == "__main__":
    main()
