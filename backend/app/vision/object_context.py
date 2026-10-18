"""Resolve tabletop candidates against causal person evidence and reviewed equipment.

This layer never changes raw model detections or their evaluation metrics.
"""
from bisect import bisect_right
from copy import deepcopy

from .reflection_filter import iou


def containment(inner, outer):
    x0, y0, x1, y1 = inner
    area = (x1-x0)*(y1-y0)
    intersection = max(0, min(x1, outer[2])-max(x0, outer[0])) * max(0, min(y1, outer[3])-max(y0, outer[1]))
    return intersection/area if area > 0 else 0.


class PersonContext:
    def __init__(self, data):
        self.data = data
        self.times = [r["t"] for r in data["rows"]]
        if self.times != sorted(set(self.times)):
            raise ValueError("Role timestamps must be strictly increasing")

    def at(self, t):
        index = bisect_right(self.times, t+1e-8)-1
        if index < 0 or t-self.times[index] > 1.1/self.data["fps"]:
            return None
        row = deepcopy(self.data["rows"][index])
        for person in row["tracks"]:
            identity = self.data["people"].get(person.get("person_id"))
            classification = person["classification"]
            if identity and identity["initialized_at"] > t:
                person["person_id"] = None
                classification["role"] = "unknown"
                classification["basis"] = "not_initialized_at_observation"
        return row


def resolve(predictions, people, anchors, t):
    kept, excluded = [], []
    for index, original in enumerate(predictions):
        p = {**original, "raw_index": index}
        if p["class"] == "clothing" and people:
            candidates = [h for h in people["tracks"] if h["score"] >= .5 and containment(p["box"], h["box"]) >= .8]
            if candidates:
                human = max(candidates, key=lambda h: containment(p["box"], h["box"]))
                p["resolution"] = {"reason": "clothing_inside_person_region", "role": human["classification"]["role"],
                    "person_id": human.get("person_id"), "person_track_id": human["id"], "role_t": people["t"],
                    "containment": containment(p["box"], human["box"]),
                    "usable_for_actions": human["association"]["usable_for_actions"],
                    "possible_reflection": human["classification"]["possible_reflection"],
                    "note": "Excluded from confirmed tabletop candidates; person overlap does not identify an action."}
                excluded.append(p)
                continue
        for anchor in anchors:
            if (anchor["interval"][0] <= t < anchor["interval"][1] and
                    p["class"] in {"desk_phone", "banknote_detector", "cash_counter", "laptop"} and
                    iou(p["box"], anchor["box"]) >= .5):
                p["resolution"] = {"reason": "reviewed_scene_equipment", "original_class": p["class"],
                    "anchor": anchor["id"], "identity_source": anchor["identity_source"],
                    "note": "Scene calibration, not an automatic classification success."}
                p["class"] = anchor["class"]
                p["class_index"] = anchor["class_index"]
                break
        kept.append(p)
    # Several raw device classes can describe the same calibrated machine.
    ordered = sorted(kept, key=lambda p: p["score"], reverse=True)
    kept = []
    for p in ordered:
        anchor = p.get("resolution", {}).get("anchor")
        if anchor and any(q.get("resolution", {}).get("anchor") == anchor for q in kept):
            excluded.append({**p, "resolution": {**p["resolution"], "reason": "duplicate_scene_equipment"}})
        else:
            kept.append(p)
    return kept, excluded


def observation_intervals(rows, fps):
    """Sum observed samples only. Never bridge missing/occluded observations."""
    result = {}
    step = 1/fps
    for row in rows:
        seen = set()
        for p in row["tracks"]:
            key = p.get("resolution", {}).get("anchor", p["id"])
            if key in seen:
                continue
            seen.add(key)
            item = result.setdefault(key, {"id": key, "class": p["class"], "intervals": [], "observed_samples": 0})
            item["observed_samples"] += 1
            intervals = item["intervals"]
            if intervals and abs(intervals[-1][1]-row["t"]) < 1e-6:
                intervals[-1][1] = round(row["t"]+step, 6)
            else:
                intervals.append([row["t"], round(row["t"]+step, 6)])
    for item in result.values():
        item["observed_seconds"] = round(item["observed_samples"]/fps, 6)
    return list(result.values())

