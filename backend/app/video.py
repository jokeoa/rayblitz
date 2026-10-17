import base64
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Frame:
    index: int
    t: float
    path: Path


def probe(video: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration", "-of", "json", str(video)],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    stream = data["streams"][0]
    return {"duration": float(data["format"]["duration"]), "width": stream["width"], "height": stream["height"]}


def sample_frames(video: Path, out_dir: Path, fps: float, width: int) -> list[Frame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video),
         "-vf", f"fps={fps},scale={width}:-2", "-q:v", "3", str(out_dir / "%05d.jpg")],
        check=True,
    )
    files = sorted(out_dir.glob("*.jpg"))
    return [Frame(i, round(i / fps, 2), p) for i, p in enumerate(files)]


def sample_segment(video: Path, out_dir: Path, start: float, end: float, fps: float, width: int) -> list[Frame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{max(start, 0):.3f}", "-t", f"{max(end - start, 0.5):.3f}", "-i", str(video),
         "-vf", f"fps={fps},scale={width}:-2", "-q:v", "2", str(out_dir / "%05d.jpg")],
        check=True,
    )
    files = sorted(out_dir.glob("*.jpg"))
    return [Frame(i, round(max(start, 0) + i / fps, 2), p) for i, p in enumerate(files)]


def frame_jpeg(video: Path, t: float) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(video),
         "-frames:v", "1", "-q:v", "3", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
        check=True, capture_output=True,
    ).stdout


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()
