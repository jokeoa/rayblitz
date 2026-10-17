import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.video import probe
from run_eval import build_items, load_labels

VARIANTS = {
    "mirror": "hflip",
    "crop": "crop=iw*0.8:ih*0.8",
    "shift": "crop=iw*0.85:ih*0.85:0:0",
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=config.ROOT / "data" / "aug")
    p.add_argument("--variants", nargs="*", default=list(VARIANTS))
    args = p.parse_args()

    items = build_items(config.ROOT / "data/open/videos", load_labels(config.ROOT / "data/open/open_labels.xlsx"))
    for name in args.variants:
        d = args.out / name
        d.mkdir(parents=True, exist_ok=True)
        for item in items:
            info = probe(item["path"])
            vf = f"{VARIANTS[name]},scale={info['width']}:{info['height']}"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(item["path"]), "-vf", vf, "-c:v", "libx264",
                            "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", "-an",
                            str(d / f"{item['name']}.mov")], check=True)
        print(f"{name}: {len(items)} videos -> {d}", flush=True)


if __name__ == "__main__":
    main()
