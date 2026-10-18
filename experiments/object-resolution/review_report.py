"""Context gallery and separate post-baseline money diagnostics."""
from collections import defaultdict
from common import ROOT, read_json, sha256, greedy_matches, iou
from context_resolution import PersonContext, resolve


def gallery(episodes, calibration):
    if read_json(ROOT/"runs/side-probe/status.json")["status"] != "complete":
        raise ValueError("Side-frame inference is incomplete")
    result=[]
    for ep in episodes:
        i=20
        result.append({"kind":"counter","video":ep["video"],"t":ep["frames"][i]["t"],
            "image":ep["frames"][i]["native"],"image_sha256":ep["frames"][i]["native_sha256"],
            "desk":ep["desk"],"raw":ep["detections"]["rows"][i]["arms"]["desk"],
            "resolved":ep["context"]["detections"]["rows"][i]["arms"]["desk"],
            "excluded":ep["context"]["detections"]["rows"][i]["excluded"]["desk"],
            "people":ep["context"]["people"][i],"anchors":calibration["videos"].get(ep["video"],[])})
    for row in read_json(ROOT/"runs/side-probe/results.json"):
        path=ROOT.parent/"role-tracking/runs/safe-side"/row["video"]/"person_tracks.json"
        data=read_json(path)
        if data["source_sha256"] != row["source_sha256"] or sha256(ROOT/"runs"/row["image"]) != row["image_sha256"]:
            raise ValueError("Extra review frame/source differs")
        people=PersonContext(data).at(row["t"])
        anchors=calibration["videos"].get(row["video"],[])
        kept,excluded=resolve(row["predictions"],people,anchors,row["t"])
        result.append({**row,"kind":"people","raw":row["predictions"],"resolved":kept,"excluded":excluded,
                       "people":people,"role_sha256":sha256(path),"anchors":anchors})
    return result


def money_diagnostics(episodes, refs):
    root=ROOT/"runs"
    for directory in ["money-probe", "semantic-probe"]:
        if read_json(root/directory/"status.json")["status"] != "complete":
            raise ValueError(f"{directory} is incomplete")
    metadata=read_json(root/"money-probe/metadata.json")
    if metadata["manifest_sha256"] != sha256(root/"manifest.json"):
        raise ValueError("Money experiment source differs")
    result={"note":metadata["note"],"arms":{},"objects":[],"rows":[],"semantic":{}}
    groups=defaultdict(list)
    for ref in refs["objects"]:
        groups[(ref["video"],ref["frame"])].append(ref)
    by_video={e["video"]:e for e in episodes}
    for ep in episodes:
        probe=read_json(root/"money-probe"/f"{ep['video']}.json")
        if probe["baseline_sha256"] != sha256(root/ep["video"]/"desk-detections.json"):
            raise ValueError("Money experiment baseline differs")
        result["rows"].append({"video":ep["video"],"rows":probe["rows"]})
    for arm in ["desk","prompt_desk","prompt_closeups"]:
        hits=[]
        for (video,frame),gt in groups.items():
            ep=by_video[video]
            if arm=="desk":
                predictions=ep["detections"]["rows"][frame]["arms"][arm]
            else:
                probe=next(x for x in result["rows"] if x["video"]==video)
                predictions=next(r for r in probe["rows"] if r["frame"]==frame)["arms"][arm]
            matches=greedy_matches([p for p in predictions if p["score"]>=.15],gt,.5)
            matched={j for _,j in matches}
            for j,ref in enumerate(gt):
                hits.append({"video":video,"entity":ref["entity"],"class":ref["class"],"hit":j in matched})
        result["arms"][arm]={"hits":sum(r["hit"] for r in hits),"total":len(hits),
            "cash_hits":sum(r["hit"] for r in hits if r["class"]=="cash"),"cash_total":sum(r["class"]=="cash" for r in hits),
            "wrapper_hits":sum(r["hit"] for r in hits if r["class"]=="packaging"),"objects":hits}
    semantic=read_json(root/"semantic-probe/results.json")
    result["semantic"]={"metadata":read_json(root/"semantic-probe/metadata.json"),"results":semantic,
        "note":"Separate candidate classification diagnostic; no inference on missed proposals. Not enabled as an automatic override."}
    for row in semantic:
        ep=by_video[row["video"]]
        if row["frame_sha256"]!=ep["frames"][row["frame"]]["native_sha256"] or row["baseline_sha256"]!=sha256(root/row["video"]/"desk-detections.json"):
            raise ValueError("Semantic probe source differs")
    result["semantic"]["references"] = []
    for ref in refs["objects"]:
        if ref["class"] not in {"cash", "packaging"}:
            continue
        near=[p for p in semantic if p["video"]==ref["video"] and p["frame"]==ref["frame"] and iou(p["proposal"]["box"],ref["box"])>=.5]
        selected=max(near,key=lambda p:iou(p["proposal"]["box"],ref["box"]),default=None)
        label=selected["parsed"]["label"] if selected and selected["parsed"] else "unknown"
        result["semantic"]["references"].append({"video":ref["video"],"entity":ref["entity"],"class":ref["class"],
                                                  "label":label,"hit":label==ref["class"]})
    return result
