import argparse
import asyncio
import time
from pathlib import Path

import httpx

LIMIT_SEC = 300


async def one(client: httpx.AsyncClient, base: str, key: str, video: Path) -> tuple[str, float, str]:
    t0 = time.time()
    with video.open("rb") as f:
        r = await client.post(f"{base}/api/v1/analyze", headers={"X-API-Key": key}, files={"file": (video.name, f, "video/quicktime")})
    r.raise_for_status()
    job_id = r.json()["job_id"]
    while True:
        await asyncio.sleep(3)
        s = (await client.get(f"{base}/api/v1/jobs/{job_id}", headers={"X-API-Key": key})).json()
        if s["status"] != "processing":
            elapsed = time.time() - t0
            summary = s.get("verdict") or s.get("error")
            types = ", ".join(f"{v['type']}@{v['timecode_sec']}" for v in s.get("violations", []))
            return video.name, elapsed, f"{s['status']} {summary} {types}"


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("videos", nargs="+", type=Path)
    p.add_argument("--base", default="http://127.0.0.1:8000")
    p.add_argument("--key", default="dev-key")
    args = p.parse_args()
    async with httpx.AsyncClient(timeout=60) as client:
        results = await asyncio.gather(*(one(client, args.base.rstrip("/"), args.key, v) for v in args.videos))
    for name, elapsed, info in results:
        flag = "OK " if elapsed < LIMIT_SEC else "LATE"
        print(f"{flag} {elapsed:6.1f}s  {name}  {info}")


if __name__ == "__main__":
    asyncio.run(main())
