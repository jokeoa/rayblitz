import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.analyzers import facts, probe as scan
from app.video import probe
from run_eval import build_items, load_labels


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--detect", type=Path, default=config.RUNS_DIR / "eval" / "detect")
    p.add_argument("--out", type=Path, default=config.RUNS_DIR / "eval" / "facts")
    p.add_argument("--rules", nargs="*")
    p.add_argument("--scan", type=Path)
    args = p.parse_args()

    items = build_items(config.ROOT / "data/open/videos", load_labels(config.ROOT / "data/open/open_labels.xlsx"))
    for item in items:
        d = args.detect / item["name"]
        rows = json.loads((d / "detections.json").read_text())
        ev = json.loads((d / "events.json").read_text())
        t0 = time.time()
        windows = []
        if args.scan:
            for w in json.loads((args.scan / item["name"] / "raw_probs.json").read_text()):
                windows += [(r, w["start"], w["end"]) for r, v in scan.scores(w["probs"]).items()
                            if r in facts.HANDS and v >= config.CANDIDATE]
        samples = await facts.facts(item["path"], rows, ev, probe(item["path"])["duration"], args.rules, windows)
        o = args.out / item["name"]
        o.mkdir(parents=True, exist_ok=True)
        (o / "facts.json").write_text(json.dumps(samples))
        label = ",".join(f"{t:g}" for t in item["times"]) if item["violation"] else "ok"
        best = {k: max((s[k] for s in samples if k in s), default=None) for k in facts.QUESTIONS}
        print(f"{item['name']:>5} {label:>6} {time.time() - t0:4.1f}s n={len(samples):>2} "
              + " ".join(f"{k}={v}" for k, v in best.items() if v is not None), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
