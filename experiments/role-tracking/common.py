"""Shared I/O and frame sampling for the tracking experiment."""
import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent


def config():
    return json.loads((ROOT / "config.json").read_text())


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def video_info(path):
    meta = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height,avg_frame_rate:format=duration", "-of", "json", str(path)
    ]))
    return {**meta["streams"][0], "duration": float(meta["format"]["duration"])}


def sampled_frames(path, fps):
    """One canonical ffmpeg sampling pass; no spatial downscale."""
    meta = video_info(path)
    width, height = meta["width"], meta["height"]
    proc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={fps}",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-"
    ], stdout=subprocess.PIPE)
    try:
        index = 0
        while True:
            raw = proc.stdout.read(width * height * 3)
            if not raw:
                break
            if len(raw) != width * height * 3:
                raise RuntimeError("Incomplete decoded frame")
            yield index, index / fps, np.frombuffer(raw, np.uint8).reshape(height, width, 3).copy()
            index += 1
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg decode failed")
    finally:
        proc.stdout.close()
        if proc.poll() is None:
            proc.terminate()
            proc.wait()


def overlap_fraction(a, b):
    x = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    y = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1]))
    return float(x*y/max(area, 1))


def sampled_frame_path(video_id, index):
    return ROOT / "runs" / video_id / "role_frames" / f"{index:06d}.jpg"
