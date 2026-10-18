"""Shared production geometry, source hashing and native-size decoding."""
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from app import config as settings
from app.video import probe

ROOT = settings.ROOT / 'references'


def config():
    return read_json(ROOT / 'config.json')


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False))
    temporary.replace(path)


def sha256(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def overlap_fraction(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    area = min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1]))
    return intersection / max(area, 1)


def sampled_frames(path, fps):
    info = probe(path)
    w, h = info['width'], info['height']
    process = subprocess.Popen(['ffmpeg', '-v', 'error', '-threads', '2', '-i', str(path),
        '-vf', f'fps={fps}', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    try:
        i = 0
        while raw := process.stdout.read(w*h*3):
            if len(raw) != w*h*3:
                raise ValueError('Incomplete decoded frame')
            yield i, i/fps, np.frombuffer(raw, np.uint8).reshape(h, w, 3).copy()
            i += 1
        if process.wait() != 0:
            raise ValueError('Video decoding failed')
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            process.wait()
