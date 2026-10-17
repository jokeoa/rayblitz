import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, detector
from app.video import Frame, sample_frames
from run_eval import build_items, load_labels


def frames_for(item: dict, frames_from: Path | None, out: Path) -> list[Frame]:
    src = frames_from / item["name"] / "frames" if frames_from else None
    if src and src.exists() and any(src.glob("*.jpg")):
        return [Frame(i, round(i / config.SAMPLE_FPS, 2), p) for i, p in enumerate(sorted(src.glob("*.jpg")))]
    return sample_frames(item["path"], out / "frames", config.SAMPLE_FPS, config.FRAME_WIDTH)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=config.RUNS_DIR / "eval" / "detect")
    p.add_argument("--frames-from", type=Path)
    args = p.parse_args()

    items = build_items(config.ROOT / "data/open/videos", load_labels(config.ROOT / "data/open/open_labels.xlsx"))
    for item in items:
        d = args.out / item["name"]
        d.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        rows = detector.detect(frames_for(item, args.frames_from, d))
        ev = detector.events(rows)
        (d / "detections.json").write_text(json.dumps(rows))
        (d / "events.json").write_text(json.dumps(ev))
        label = ",".join(f"{t:g}" for t in item["times"]) if item["violation"] else "ok"
        print(f"{item['name']:>5} {label:>6} {time.time() - t0:4.1f}s zone={'yes' if ev['zone'] else 'NO '} "
              f"leaves={ev['leaves']} empty={ev['empty']}", flush=True)


if __name__ == "__main__":
    main()
