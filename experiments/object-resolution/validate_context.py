"""Validate source alignment and every context decision without model reruns."""
from collections import Counter
from common import ROOT, read_json, sha256
from context_resolution import containment, observation_intervals


def main():
    root=ROOT/"runs"
    viewer=read_json(root/"viewer-data.json")
    counts=Counter()
    for ep in viewer["episodes"]:
        context=ep["context"]
        assert context["role_sha256"]==sha256(context["role_source"])
        assert context["code_sha256"]==sha256(ROOT/"context_resolution.py")
        assert context["calibration_sha256"]==sha256(ROOT/"scene_objects.json")
        for key,name in [("detections_sha256","desk-detections.json"),("tracks_sha256","desk-tracks.json")]:
            assert context[key]==sha256(root/ep["video"]/name)
        for index,row in enumerate(context["detections"]["rows"]):
            assert row["t"]==ep["frames"][index]["t"]
            people=context["people"][index]
            if people:
                assert people["t"] <= row["t"]+1e-8
                assert row["t"]-people["t"]<=.11
            for arm, kept in row["arms"].items():
                raw=ep["detections"]["rows"][index]["arms"][arm]
                excluded=row["excluded"][arm]
                assert sorted(p["raw_index"] for p in kept+excluded)==list(range(len(raw)))
                for p in kept+excluded:
                    source=raw[p["raw_index"]]
                    assert p["box"]==source["box"] and p["score"]==source["score"]
                    decision=p.get("resolution",{})
                    if decision.get("reason")=="clothing_inside_person_region":
                        human=next(h for h in people["tracks"] if h["id"]==decision["person_track_id"])
                        assert source["class"]=="clothing" and containment(source["box"],human["box"])>=.8
                        assert p in excluded
                    elif p["class"] != source["class"]:
                        assert decision["original_class"]==source["class"] and p["class"]=="cash_counter"
                counts["candidate_decisions"]+=len(raw)
            counts["frames"]+=1
        for fps,arms in context["tracks"]["arms"].items():
            for arm,run in arms.items():
                for row in run["rows"]:
                    decisions={p["raw_index"]:p for p in context["detections"]["rows"][row["frame"]]["arms"][arm]}
                    for track in row["tracks"]:
                        source=decisions[track["detection_index"]]
                        assert track["observed_box"]==source["box"] and track["class"]==source["class"]
                        counts["supported_track_observations"]+=1
                assert context["durations"][fps][arm]==observation_intervals(run["rows"],int(fps))
                assert all(0<=p["observed_seconds"]<=4 for p in context["durations"][fps][arm])
    for row in viewer["gallery"]:
        assert sha256(root/row["image"])==row["image_sha256"]
        counts["review_images"]+=1
    for directory in ["money-probe","side-probe","semantic-probe"]:
        assert read_json(root/directory/"status.json")["status"]=="complete"
        metadata=read_json(root/directory/"metadata.json")
        if directory=="money-probe":
            for name,digest in metadata["code"].items():
                assert sha256(root/directory/name)==digest
        else:
            assert sha256(root/directory/(directory.replace("-","_")+".py"))==metadata["code_sha256"]
    assert len(viewer["money"]["rows"])==11
    assert sum(len(x["rows"]) for x in viewer["money"]["rows"])==44
    assert len(viewer["money"]["semantic"]["results"])==12
    print(dict(counts))
    print("Context integrity passed; this is not a measurement of detection accuracy.")


if __name__=="__main__":
    main()
