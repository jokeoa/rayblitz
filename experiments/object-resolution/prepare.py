"""Freeze the selected source episodes and decode both resolutions together."""
import argparse
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw
from common import ROOT, read_json, sha256, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("/Users/jokeoa/Downloads/open/videos"))
    args = parser.parse_args()
    cfg = read_json(ROOT / "config.json")
    out = ROOT / "runs"
    if (out / "manifest.json").exists():
        raise SystemExit("An experiment already exists; use a new directory for a changed run.")
    paths = {p.stem.replace("Х", "X"): p for p in args.data.glob("*.mov")}
    manifest = {"config": cfg, "config_sha256": sha256(ROOT / "config.json"), "episodes": [],
                "scope": "Development episodes selected from source content. Resolution-only comparison at 10 fps, not the complete production service. PNG in every arm isolates resize from JPEG compression.",
                "ground_truth": "No human-confirmed exhaustive object labels yet."}
    for ep in cfg["episodes"]:
        video = ep["video"]
        source = paths[video]
        directory = out / video
        for variant in ("native", "reduced"):
            (directory / variant).mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-ss", str(ep["start"]), "-i", str(source),
            "-filter_complex", f"fps={cfg['fps']},split=2[native][low];[low]scale={cfg['reduced_width']}:-2[reduced]",
            "-map", "[native]", "-t", str(cfg["duration"]), str(directory / "native/%04d.png"),
            "-map", "[reduced]", "-t", str(cfg["duration"]), str(directory / "reduced/%04d.png"),
        ], check=True)
        native = sorted((directory / "native").glob("*.png"))
        reduced = sorted((directory / "reduced").glob("*.png"))
        if len(native) != len(reduced) or len(native) != cfg["fps"] * cfg["duration"]:
            raise ValueError(f"Unexpected frame counts in {video}")
        with Image.open(native[0]) as image:
            size = image.size
        rows = [{"frame": i, "t": ep["start"] + i / cfg["fps"],
                 "native": str(n.relative_to(out)), "native_sha256": sha256(n),
                 "reduced": str(r.relative_to(out)), "reduced_sha256": sha256(r)}
                for i, (n, r) in enumerate(zip(native, reduced))]
        manifest["episodes"].append({**ep, "source_sha256": sha256(source),
                                     "source_filename": source.name, "size": size, "frames": rows})
        print(video, len(rows), "paired frames", flush=True)
    write_json(out / "manifest.json", manifest)
    sheet = Image.new("RGB", (4 * 464, ((len(manifest["episodes"]) + 3) // 4) * 880), "#f0eee9")
    draw = ImageDraw.Draw(sheet)
    for i, ep in enumerate(manifest["episodes"]):
        frame = ep["frames"][20]
        image = Image.open(out / frame["native"])
        x, y = i % 4 * 464, i // 4 * 880
        sheet.paste(image, (x, y + 32))
        draw.text((x + 10, y + 8), f"{ep['video']} @ {frame['t']:.1f}s", fill="black")
    sheet.save(out / "source-overview.jpg", quality=95)


if __name__ == "__main__":
    main()
