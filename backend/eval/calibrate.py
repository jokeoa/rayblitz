import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, detector, rules
from app.analyzers import facts
from app.analyzers.probe import scores as window_scores
from run_eval import build_items, load_labels

MIN_T, MAX_T, EPS = 0.3, 0.95, 0.01
FLOORS = {"none": 0.3, "window": 0.1}


def scores(d: Path, norm: str, ev: dict | None = None) -> tuple[dict[str, float], dict[str, float]]:
    out = {r: -1.0 for r in rules.rule_ids()}
    leave = {}
    for w in json.loads((d / "raw_probs.json").read_text()):
        for r, p in window_scores(w["probs"], norm).items():
            t = None
            if ev and r in detector.LEAVE_RULES:
                allowed, t = detector.gate(ev, w["start"], w["end"])
                if not allowed:
                    continue
            if r in out and p > out[r]:
                out[r] = p
                if t is not None:
                    leave[r] = t
    return out, leave


def event_time(d: Path, rule_id: str) -> float | None:
    events = [e for e in json.loads((d / "raw_events.json").read_text()) if e["rule_id"] == rule_id]
    return max(events, key=lambda e: e["confidence"])["t"] if events else None


def when(s: dict, rule_id: str) -> float | None:
    return s["leave"].get(rule_id, event_time(s["dir"], rule_id))


def fit(samples: list[dict], margin: float, min_t: float = MIN_T) -> dict[str, float]:
    neg = [s for s in samples if not s["violation"]]
    return {
        r: min(MAX_T, max(min_t, max((s["scores"][r] for s in neg), default=-1.0) + margin))
        for r in rules.rule_ids()
    }


def predict(s: dict, th: dict[str, float]) -> tuple[bool, str | None]:
    over = {r: s["scores"][r] - th[r] for r in th if s["scores"][r] >= th[r]}
    return (True, max(over, key=over.get)) if over else (False, None)


def report(samples: list[dict], preds: list[tuple[bool, str | None]], title: str) -> None:
    tp = sum(p and s["violation"] for s, (p, _) in zip(samples, preds))
    fp = sum(p and not s["violation"] for s, (p, _) in zip(samples, preds))
    fn = sum(not p and s["violation"] for s, (p, _) in zip(samples, preds))
    tn = len(samples) - tp - fp - fn
    errs = []
    for s, (p, r) in zip(samples, preds):
        if p and s["violation"] and s["times"]:
            t = when(s, r)
            if t is not None:
                errs.append(min(abs(t - x) for x in s["times"]))
    errs.sort()
    med = errs[len(errs) // 2] if errs else None
    print(f"{title}: acc={(tp + tn) / len(samples):.3f} tp={tp} fp={fp} fn={fn} tn={tn} "
          f"t_err_median={med} within2s={sum(e <= 2 for e in errs)}/{len(errs)}")


CODE_ALIASES = {"E-04": "D-12"}


def load_typed() -> dict[str, dict]:
    f = Path(__file__).resolve().parent / "labels_typed.json"
    if not f.exists():
        return {}
    by_code = {r["code"]: r["id"] for r in rules.rules() if r.get("code")}
    out = {}
    for name, v in json.loads(f.read_text(encoding="utf-8"))["videos"].items():
        codes = [e["code"] for e in v["events"]]
        mapped = {by_code.get(CODE_ALIASES.get(c, c)) for c in codes} - {None}
        out[name] = {"codes": codes, "rules": mapped, "status": v["status"]}
    return out


def report_types(samples: list[dict], preds: list[tuple[bool, str | None]], typed: dict, min_t: float,
                 rest) -> None:
    hits: dict[str, list[int]] = {}
    top_ok = top_n = 0
    for s, (pred, top_rule) in zip(samples, preds):
        lab = typed.get(s["name"])
        if not lab or not lab["rules"]:
            continue
        th = fit(rest(s), EPS, min_t)
        for r in lab["rules"]:
            hits.setdefault(r, []).append(int(s["scores"][r] >= th[r]))
        if pred:
            top_n += 1
            top_ok += top_rule in lab["rules"]
    print(f"\ntype of top event matches label: {top_ok}/{top_n} detected videos")
    print("per-rule recall on labeled events (leave-one-out):")
    for r, h in sorted(hits.items()):
        print(f"  {r:>24} {sum(h)}/{len(h)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, default=config.RUNS_DIR / "eval" / "probe")
    p.add_argument("--margin", type=float, default=EPS)
    p.add_argument("--write", type=Path)
    p.add_argument("--norm", choices=sorted(FLOORS), default=config.SCORE_NORM)
    p.add_argument("--min-t", type=float)
    p.add_argument("--detect", type=Path)
    p.add_argument("--facts", type=Path, nargs="*")
    p.add_argument("--composite", nargs="*", default=config.COMPOSITE_RULES)
    p.add_argument("--groups", type=Path)
    args = p.parse_args()
    args.min_t = FLOORS[args.norm] if args.min_t is None else args.min_t

    items = build_items(config.ROOT / "data/open/videos", load_labels(config.ROOT / "data/open/open_labels.xlsx"))
    samples = []
    for i in items:
        d = args.run / i["name"]
        if (d / "raw_probs.json").exists():
            ev = json.loads((args.detect / i["name"] / "events.json").read_text()) if args.detect else None
            sc, leave = scores(d, args.norm, ev)
            if args.facts:
                fs = [x for f in args.facts for x in json.loads((f / i["name"] / "facts.json").read_text())]
                for r in args.composite:
                    sc[r], leave[r] = -1.0, None
                for r, (p, t) in facts.composite(fs, ev).items():
                    if r in args.composite:
                        sc[r], leave[r] = p, t
                leave = {r: t for r, t in leave.items() if t is not None}
            samples.append({**i, "dir": d, "scores": sc, "leave": leave})
    print(f"videos: {len(samples)}")

    print("\nmax score per rule (neg max / pos max):")
    for r in rules.rule_ids():
        neg = max((s["scores"][r] for s in samples if not s["violation"]), default=0)
        pos = max((s["scores"][r] for s in samples if s["violation"]), default=0)
        print(f"  {r:>26} {neg:.3f} / {pos:.3f}")

    groups = json.loads(args.groups.read_text()) if args.groups else {}

    def rest(s: dict) -> list[dict]:
        return [x for x in samples if groups.get(x["name"], x["name"]) != groups.get(s["name"], s["name"])]

    th = fit(samples, args.margin, args.min_t)
    report(samples, [predict(s, th) for s in samples], "in-sample")
    loo = [predict(s, fit(rest(s), args.margin, args.min_t)) for s in samples]
    report(samples, loo, "leave-one-setup-out" if groups else "leave-one-out")

    typed = load_typed()
    if typed:
        report_types(samples, loo, typed, args.min_t, rest)

    print("\nper video (leave-one-out):")
    for s, (pred, r) in zip(samples, loo):
        label = f"V@{','.join(f'{t:g}' for t in s['times'])}" if s["violation"] else "ok"
        codes = ",".join(typed.get(s["name"], {}).get("codes", []))
        top3 = sorted(s["scores"].items(), key=lambda kv: -kv[1])[:3]
        mark = "" if pred == s["violation"] else "  <-- WRONG"
        t = when(s, r) if r else None
        print(f"{'/'.join(s['aliases']):>10} {label:>9} {codes:>10} pred={r or '-'}@{t}  top: "
              + ", ".join(f"{k}={v:.2f}" for k, v in top3) + mark)

    if args.write:
        args.write.write_text(json.dumps(th, indent=1), encoding="utf-8")
        print(f"\nthresholds written to {args.write}")


if __name__ == "__main__":
    main()
