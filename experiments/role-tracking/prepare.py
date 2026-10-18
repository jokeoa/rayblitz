"""Inspect extracted source videos and make a contact sheet; never edit originals."""
import argparse
import io
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


def metadata(path):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height,avg_frame_rate:format=duration", "-of", "json", str(path)
    ]))


def frame(path, timestamp):
    return Image.open(io.BytesIO(subprocess.check_output([
        "ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", str(path),
        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"
    ]))).convert("RGB")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).parent)
    args = p.parse_args()
    manifest = json.loads((args.root / "data/manifest.json").read_text())
    seen, rows = set(), []
    for item in manifest:
        if item["sha256"] in seen:
            continue
        seen.add(item["sha256"])
        path = args.root / "data" / (item["id"] + ".mov")
        meta = metadata(path)
        item.update(duration=float(meta["format"]["duration"]), **meta["streams"][0])
        rows.append(item)
    sheet = Image.new("RGB", (1280, ((len(rows)+3)//4)*220), "#111827")
    draw = ImageDraw.Draw(sheet)
    for i, item in enumerate(rows):
        img = frame(args.root / "data" / (item["id"]+".mov"), item["duration"]*.35)
        img.thumbnail((314, 184))
        x, y = (i%4)*320, (i//4)*220
        sheet.paste(img, (x+(320-img.width)//2, y))
        draw.text((x+5,y+187), f'{item["id"]} | {item["duration"]:.1f}s | {item["width"]}x{item["height"]}', fill="white")
    (args.root / "runs").mkdir(exist_ok=True)
    sheet.save(args.root / "runs/source-overview.jpg", quality=90)
    (args.root / "data/unique-videos.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print(json.dumps({"unique_videos":len(rows),"seconds":sum(r["duration"] for r in rows)}))


if __name__ == "__main__":
    main()
