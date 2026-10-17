import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.pipeline import thresholds
from calibrate import load_typed
from run_eval import build_items, load_labels

LIMIT_SEC = 300


async def submit(client: httpx.AsyncClient, base: str, key: str, video: Path) -> dict:
    t0 = time.time()
    with video.open("rb") as f:
        r = await client.post(f"{base}/api/v1/analyze", headers={"X-API-Key": key},
                              files={"file": (video.name, f, "video/quicktime")})
    r.raise_for_status()
    job_id = r.json()["job_id"]
    while True:
        await asyncio.sleep(3)
        s = (await client.get(f"{base}/ui/jobs/{job_id}")).json()
        if s["status"] != "processing":
            s["wall_sec"] = round(time.time() - t0, 1)
            for v in s.get("violations", []):
                v["evidence_frames"] = len(v["evidence_frames"])
            return s


async def run_all(items: list[dict], out: Path, base: str, key: str, parallel: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(parallel)
    async with httpx.AsyncClient(timeout=120) as client:
        async def one(item):
            f = out / f"{item['name']}.json"
            if f.exists():
                return
            async with sem:
                s = await submit(client, base, key, item["path"])
            f.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
            print(f"{item['name']}: {s['status']} {s['wall_sec']}s", flush=True)

        await asyncio.gather(*(one(i) for i in items))


def top(s: dict, th: dict[str, float]) -> dict | None:
    vs = s.get("violations") or []
    return max(vs, key=lambda v: v["confidence"] - th.get(v["rule"]["id"], 0.0)) if vs else None


def score(items: list[dict], out: Path, typed: dict, th: dict[str, float]) -> dict[str, tuple[bool, dict | None]]:
    tp = fp = fn = tn = type_ok = exact = late = failed = 0
    errs, preds = [], {}
    for item in items:
        s = json.loads((out / f"{item['name']}.json").read_text(encoding="utf-8"))
        failed += s["status"] != "done"
        late += s["wall_sec"] >= LIMIT_SEC
        v = top(s, th)
        preds[item["name"]] = (v is not None, v)
        if v and item["violation"]:
            tp += 1
            right_type = v["rule"]["id"] in typed.get(item["name"], {}).get("rules", set())
            type_ok += right_type
            if item["times"]:
                err = min(abs(v["timecode_sec"] - t) for t in item["times"])
                errs.append(err)
                exact += right_type and err <= 2
        elif item["violation"]:
            fn += 1
        elif v:
            fp += 1
        else:
            tn += 1
    errs.sort()
    walls = sorted(json.loads((out / f"{i['name']}.json").read_text(encoding="utf-8"))["wall_sec"] for i in items)
    print(f"{out.name}: acc={(tp + tn) / len(items):.3f} tp={tp} fp={fp} fn={fn} tn={tn} type={type_ok}/{tp} "
          f"type_and_time2s={exact}/{tp + fn} t_err_median={errs[len(errs) // 2] if errs else None} "
          f"wall_max={walls[-1]}s late={late} failed={failed}")
    return preds


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--videos", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--score", type=Path, nargs="*")
    p.add_argument("--base", default="http://127.0.0.1:8000")
    p.add_argument("--key", default=config.API_KEY)
    p.add_argument("--parallel", type=int, default=2)
    args = p.parse_args()

    items = build_items(config.ROOT / "data/open/videos", load_labels(config.ROOT / "data/open/open_labels.xlsx"))
    if args.out:
        run_items = [dict(i, path=args.videos / f"{i['name']}.mov") if args.videos else i for i in items]
        asyncio.run(run_all(run_items, args.out, args.base.rstrip("/"), args.key, args.parallel))
    dirs = args.score or [args.out]
    items = [i for i in items if all((d / f"{i['name']}.json").exists() for d in dirs)]
    typed, th = load_typed(), thresholds()
    preds = [score(items, d, typed, th) for d in dirs]
    print()
    for item in items:
        label = "V@" + ",".join(f"{t:g}" for t in item["times"]) if item["violation"] else "ok"
        codes = ",".join(typed.get(item["name"], {}).get("codes", []))
        cells = []
        for pr in preds:
            hit, v = pr[item["name"]]
            mark = "" if hit == item["violation"] else "!"
            cells.append(f"{(v['rule']['code'] + '@' + format(v['timecode_sec'], 'g')) if v else '-'}{mark}")
        print(f"{'/'.join(item['aliases']):>10} {label:>9} {codes:>12}  " + "  ".join(f"{c:>12}" for c in cells))


if __name__ == "__main__":
    main()
