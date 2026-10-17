import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.analyzers import atoms
from run_eval import build_items, load_labels, norm


async def analyze_all(items: list[dict], out: Path, force: bool, parallel: int) -> None:
    sem = asyncio.Semaphore(parallel)

    async def one(item):
        d = out / item["name"]
        if (d / "raw_events.json").exists() and not force:
            return
        async with sem:
            t0 = time.time()
            d.mkdir(parents=True, exist_ok=True)
            await atoms.analyze(item["path"], d)
            (d / "elapsed.txt").write_text(f"{time.time() - t0:.1f}")
            print(f"{item['name']}: {time.time() - t0:.1f}s", flush=True)

    await asyncio.gather(*(one(i) for i in items))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=config.RUNS_DIR / "eval" / "atoms")
    p.add_argument("--only", nargs="*")
    p.add_argument("--force", action="store_true")
    p.add_argument("--parallel", type=int, default=2)
    args = p.parse_args()

    items = build_items(config.ROOT / "data/open/videos", load_labels(config.ROOT / "data/open/open_labels.xlsx"))
    if args.only:
        items = [i for i in items if set(i["aliases"]) & {norm(x) for x in args.only}]
    asyncio.run(analyze_all(items, args.out, args.force, args.parallel))


if __name__ == "__main__":
    main()
