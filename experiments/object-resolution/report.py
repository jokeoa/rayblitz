"""Local evidence viewer and explicitly limited source-reference diagnostics."""
import collections
import json
import shutil
import statistics

from common import ROOT, greedy_matches, iou, read_json, sha256, write_json
from context_resolution import build_episode
from review_report import gallery, money_diagnostics

ARMS = ("reduced", "native", "tiles", "desk")


def diagnostics(manifest, episodes, refs):
    threshold = manifest["config"]["display_score"]
    by_video = {e["video"]: e for e in episodes}
    summary = {"score_threshold": threshold, "reference_scope": refs["scope"],
               "formal_detection_precision": None, "IDF1": None, "HOTA": None,
               "reason": "No exhaustive human boxes or persistent object identities. Selected development references cannot establish whole-dataset accuracy.",
               "arms": {}, "objects": [], "negative_checks": [], "static_reference_tracks": []}
    for arm in ARMS:
        timing = [r["seconds"][arm] for ep in episodes for r in ep["detections"]["rows"]]
        counts = collections.Counter(p["class"] for ep in episodes for r in ep["detections"]["rows"]
                                     for p in r["arms"][arm] if p["score"] >= threshold)
        summary["arms"][arm] = {"inference_seconds": sum(timing), "median_ms_per_frame": statistics.median(timing) * 1000,
                                 "prediction_count_by_class": dict(counts), "selected_reference_hits_iou50": 0,
                                 "selected_reference_hits_iou30": 0, "human_identity_hits_iou50": 0}
    for ref in refs["objects"]:
        row = by_video[ref["video"]]["detections"]["rows"][ref["frame"]]
        item = {**ref, "pixel_width": ref["box"][2] - ref["box"][0],
                "pixel_height": ref["box"][3] - ref["box"][1], "arms": {}}
        for arm in ARMS:
            candidates = [p for p in row["arms"][arm] if p["class"] == ref["class"]]
            near = [p for p in candidates if iou(p["box"], ref["box"]) >= .3]
            passing = [p for p in near if p["score"] >= threshold]
            best = max(passing, key=lambda p: iou(p["box"], ref["box"]), default=None)
            item["arms"][arm] = {"best_candidate_score_iou30": max((p["score"] for p in near), default=None),
                                  "best_passing_iou": iou(best["box"], ref["box"]) if best else 0,
                                  "matched_iou50": False,
                                  "nearby_other_classes": sorted(
                                      [{"class": p["class"], "score": p["score"], "iou": iou(p["box"], ref["box"])}
                                       for p in row["arms"][arm] if p["class"] != ref["class"] and p["score"] >= threshold
                                       and iou(p["box"], ref["box"]) >= .3],
                                      key=lambda p: p["score"], reverse=True)[:3]}
        summary["objects"].append(item)
    # Match jointly so a single merged stamp box cannot count as two detections.
    groups = collections.defaultdict(list)
    for ref in refs["objects"]:
        groups[(ref["video"], ref["frame"])].append(ref)
    for (vid, frame), gt in groups.items():
        row = by_video[vid]["detections"]["rows"][frame]
        for arm in ARMS:
            pred = [p for p in row["arms"][arm] if p["score"] >= threshold]
            for cutoff in (.3, .5):
                matches = greedy_matches(pred, gt, cutoff)
                summary["arms"][arm][f"selected_reference_hits_iou{round(cutoff*100)}"] += len(matches)
                if cutoff == .5:
                    summary["arms"][arm]["human_identity_hits_iou50"] += sum(gt[j]["identity_source"] == "human" for _, j in matches)
                    for _, j in matches:
                        target = next(r for r in summary["objects"] if r["video"] == vid and r["entity"] == gt[j]["entity"])
                        target["arms"][arm]["matched_iou50"] = True
    summary["reference_count"] = len(refs["objects"])
    summary["human_identity_count"] = sum(r["identity_source"] == "human" for r in refs["objects"])
    for ref in refs["negatives"]:
        row = by_video[ref["video"]]["detections"]["rows"][ref["frame"]]
        checks = {}
        x0, y0, x1, y1 = ref["region"]
        for arm in ARMS:
            checks[arm] = [p for p in row["arms"][arm] if p["class"] == ref["class"] and p["score"] >= threshold
                           and x0 <= (p["box"][0] + p["box"][2]) / 2 <= x1
                           and y0 <= (p["box"][1] + p["box"][3]) / 2 <= y1]
        summary["negative_checks"].append({**ref, "arms": checks})
    for ref in refs["objects"]:
        if "static_interval" not in ref:
            continue
        episode = by_video[ref["video"]]
        for fps, modes in episode["tracks"]["arms"].items():
            for arm in ARMS:
                seen = []
                for row in modes[arm]["rows"]:
                    if not ref["static_interval"][0] <= row["frame"] <= ref["static_interval"][1]:
                        continue
                    peers = [g for g in refs["objects"] if g["video"] == ref["video"] and "static_interval" in g
                             and g["static_interval"][0] <= row["frame"] <= g["static_interval"][1]]
                    matches = greedy_matches(row["tracks"], peers, .3)
                    hit = next((row["tracks"][i]["id"] for i, j in matches if peers[j]["entity"] == ref["entity"]), None)
                    seen.append(hit)
                summary["static_reference_tracks"].append({"video": ref["video"], "entity": ref["entity"], "fps": int(fps),
                    "arm": arm, "sampled_frames": len(seen), "matched_frames": sum(x is not None for x in seen),
                    "distinct_matched_ids": len(set(x for x in seen if x is not None)),
                    "note": "Assistant static-box diagnostic at IoU>=0.3, not HOTA/IDF1 or general identity accuracy."})
    return summary


def main():
    root = ROOT / "runs"
    manifest = read_json(root / "manifest.json")
    scope = read_json(root / "desk-scope.json")
    refs = read_json(ROOT / "reference_objects.json")
    calibration = read_json(ROOT / "scene_objects.json")
    episodes = []
    for ep in manifest["episodes"]:
        if ep["video"] not in scope["videos"]:
            continue
        detected = read_json(root / ep["video"] / "desk-detections.json")
        tracks = read_json(root / ep["video"] / "desk-tracks.json")
        if detected["config_sha256"] != manifest["config_sha256"] or tracks["detections_sha256"] != sha256(root / ep["video"] / "desk-detections.json") or detected["scope_sha256"] != sha256(root / "desk-scope.json"):
            raise ValueError("Mismatched provenance")
        context = build_episode(ep, detected, tracks, calibration)
        write_json(root / ep["video"] / "context.json", context)
        episodes.append({**ep, "desk": scope["videos"][ep["video"]], "detections": detected, "tracks": tracks,
                         "context": context})
    summary = diagnostics(manifest, episodes, refs)
    summary["desk_scope"] = scope
    summary["reference_objects_sha256"] = sha256(ROOT / "reference_objects.json")
    summary["human_labels_sha256"] = sha256(ROOT / "human_labels.json")
    summary["context"] = {"automatic_metrics_unchanged": True,
        "note": "Person and scene overrides are a separate observation layer, not detector successes. Track IDs remain original.",
        "scene_objects_sha256": sha256(ROOT/"scene_objects.json"),
        "excluded_clothing_at_015": sum(p["score"] >= .15 and p["class"] == "clothing"
            for ep in episodes for row in ep["context"]["detections"]["rows"] for p in row["excluded"]["desk"]),
        "equipment_class_changes_at_015": sum(p["score"] >= .15 and p.get("resolution", {}).get("original_class", p["class"]) != p["class"]
            for ep in episodes for row in ep["context"]["detections"]["rows"] for p in row["arms"]["desk"])}
    money = money_diagnostics(episodes, refs)
    write_json(root / "money-summary.json", money)
    write_json(root / "summary.json", summary)
    payload = {"config": manifest["config"], "episodes": episodes, "summary": summary,
               "references": refs, "human_labels": read_json(ROOT / "human_labels.json"),
               "gallery": gallery(episodes, calibration), "money": money}
    temporary = root / "viewer-data.json.tmp"
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    temporary.replace(root / "viewer-data.json")
    shutil.copy(ROOT / "viewer.html", root / "index.html")
    shutil.copy(ROOT / "README.md", root / "README.md")
    for arm, row in summary["arms"].items():
        print(arm, f"{row['selected_reference_hits_iou50']}/{summary['reference_count']} selected reference hits",
              round(row["median_ms_per_frame"]), "ms/frame")


if __name__ == "__main__":
    main()
