import argparse
import asyncio
import base64
import os
import time
from pathlib import Path

import httpx

LIMIT_SEC = 300
TOP = {"job_id", "status", "verdict", "violations"}
VIOLATION = {"type", "timecode_sec", "description", "evidence_frames"}
FRAME = {"timestamp_sec", "image_base64"}


def check_result(s: dict) -> list[str]:
    errors = []
    if set(s) != TOP:
        errors.append(f"top-level keys {sorted(s)}")
    if s.get("verdict") not in ("violation", "no_violation"):
        errors.append(f"verdict {s.get('verdict')!r}")
    vs = s.get("violations", [])
    if (s.get("verdict") == "violation") != bool(vs):
        errors.append("verdict does not match violations")
    for v in vs:
        if set(v) != VIOLATION:
            errors.append(f"violation keys {sorted(v)}")
        if not isinstance(v.get("timecode_sec"), (int, float)) or not v.get("type") or not v.get("description"):
            errors.append("empty type, description or non-numeric timecode")
        frames = v.get("evidence_frames", [])
        if not 1 <= len(frames) <= 3:
            errors.append(f"{len(frames)} evidence frames")
        for f in frames:
            if set(f) != FRAME or not isinstance(f.get("timestamp_sec"), (int, float)):
                errors.append(f"frame keys {sorted(f)}")
            elif not base64.b64decode(f["image_base64"], validate=True).startswith(b"\xff\xd8"):
                errors.append("frame is not a JPEG")
    return errors


async def analyze(client: httpx.AsyncClient, base: str, key: str, video: Path) -> tuple[float, dict]:
    t0 = time.time()
    with video.open("rb") as f:
        r = await client.post(f"{base}/api/v1/analyze", headers={"X-API-Key": key},
                              files={"file": (video.name, f, "video/quicktime")})
    r.raise_for_status()
    job_id = r.json()["job_id"]
    while True:
        await asyncio.sleep(2)
        s = (await client.get(f"{base}/api/v1/jobs/{job_id}", headers={"X-API-Key": key})).json()
        if s["status"] != "processing":
            return time.time() - t0, s


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("videos", nargs="+", type=Path)
    p.add_argument("--base", default="http://127.0.0.1:8000")
    p.add_argument("--key", default=os.environ.get("API_KEY", ""))
    args = p.parse_args()
    base = args.base.rstrip("/")

    async with httpx.AsyncClient(timeout=120) as client:
        probes = {
            "no key": await client.post(f"{base}/api/v1/analyze", files={"file": ("a.mov", b"x")}),
            "wrong key": await client.get(f"{base}/api/v1/jobs/00000000", headers={"X-API-Key": "wrong"}),
            "not a video": await client.post(f"{base}/api/v1/analyze", headers={"X-API-Key": args.key},
                                             files={"file": ("a.txt", b"x")}),
            "unknown job": await client.get(f"{base}/api/v1/jobs/00000000", headers={"X-API-Key": args.key}),
        }
        expected = {"no key": 401, "wrong key": 401, "not a video": 415, "unknown job": 404}
        for name, r in probes.items():
            print(f"{'OK ' if r.status_code == expected[name] else 'BAD'} {name}: {r.status_code}")
        results = await asyncio.gather(*(analyze(client, base, args.key, v) for v in args.videos))

    for video, (elapsed, s) in zip(args.videos, results):
        errors = check_result(s) if s["status"] == "done" else [f"status {s['status']}: {s.get('error')}"]
        if elapsed >= LIMIT_SEC:
            errors.append(f"took {elapsed:.0f} s")
        found = ", ".join(f"{v['type']}@{v['timecode_sec']}" for v in s.get("violations", []))
        print(f"{'OK ' if not errors else 'BAD'} {elapsed:6.1f}s {video.name}: {s.get('verdict')} {found}")
        for e in errors:
            print(f"      {e}")


if __name__ == "__main__":
    asyncio.run(main())
