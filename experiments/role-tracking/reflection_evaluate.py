"""Evaluate retained input boxes and tracker coverage; labels never feed filtering."""
from common import ROOT,config,read_json,write_json
from reflection_filter import iou


def main():
    labels=read_json(ROOT/"reflection_assistant_labels.json")
    human=read_json(ROOT/"reflection_human_labels.json")
    # Human labels replace assistant guesses on the same candidate, not inputs.
    indexed={(r["video"],r["frame"],r["detection_id"]):r for r in labels}
    for row in human: indexed[(row["video"],row["frame"],row["detection_id"])]=row
    outcomes=[]
    videos={}
    for vid in config()["videos"]:
        src=ROOT/"runs"/vid;out=ROOT/"runs/reflections"/vid
        videos[vid]={
            "decisions":read_json(out/"decisions.json")["rows"],
            **{f"{name}_{stage}":read_json(directory/f"{name}.json")["rows"] for name in ["bytetrack","botsort_reid"] for stage,directory in [("before",src),("after",out)]},
        }
    for row in indexed.values():
        data=videos[row["video"]];f=row["frame"]
        removed={x["detection_id"] for x in data["decisions"][f]["removed"]}
        tracks={}
        for name in ["bytetrack","botsort_reid"]:
            stages={}
            for stage in ["before","after"]:
                matches=[tr for tr in data[f"{name}_{stage}"][f]["tracks"] if iou(tr["box"],row["box"])>=.5]
                stages[stage]={"covered":bool(matches),"ids":[tr["id"] for tr in matches]}
            tracks[name]=stages
        outcomes.append({**row,"input_detection_removed":row["detection_id"] in removed,"track_coverage_iou_0_5":tracks})
    summaries=[]
    for label in ["direct","reflection","not_person","uncertain"]:
        selected=[r for r in outcomes if r["label"]==label]
        by_method={}
        for name in ["bytetrack","botsort_reid"]:
            before=sum(r["track_coverage_iou_0_5"][name]["before"]["covered"] for r in selected)
            after=sum(r["track_coverage_iou_0_5"][name]["after"]["covered"] for r in selected)
            lost=[{k:r[k] for k in ["video","frame","t","detection_id"]} for r in selected if r["track_coverage_iou_0_5"][name]["before"]["covered"] and not r["track_coverage_iou_0_5"][name]["after"]["covered"]]
            by_method[name]={"before_covered":before,"after_covered":after,"lost_coverage":lost}
        summaries.append({"label":label,"annotated_boxes":len(selected),"human_boxes":sum(r["annotator"]=="human_user" for r in selected),"input_boxes_removed":sum(r["input_detection_removed"] for r in selected),"track_coverage":by_method})
    occlusion=[]
    for f in [135,136,137,138,140,150,200]:
        # Detection IDs are frame-local confidence ranks, not identities.
        # At 13.7s the customer becomes D0; at 20s the entrant makes them D2.
        di={135:1,136:1,137:0,138:1,140:1,150:1,200:2}[f]
        row={"video":"X-18","frame":f,"t":f/10,"source_detection_id":di}
        for name in ["bytetrack","botsort_reid"]:
            row[name]={stage:[tr["id"] for tr in videos["X-18"][f"{name}_{stage}"][f]["tracks"] if tr["det_idx"]==di] for stage in ["before","after"]}
        occlusion.append(row)
    result={"scope":"Diagnostic audit of cached detection boxes on 24 selected frames. Six labels are from the user; others are assistant visual reviews. This is not complete person ground truth, unbiased recall or held-out validation. Coverage is measured per annotated box, not per distinct person; partial/duplicate boxes may describe one person.","summary":summaries,"outcomes":outcomes,"human_outcomes":[r for r in outcomes if r["annotator"]=="human_user"],"frames":len({(r["video"],r["frame"]) for r in outcomes}),"occlusion_case_X18":occlusion}
    observations=read_json(ROOT/"runs/reflections/X-18/observations.json")["observations"]
    observed=next(o for o in observations if o["frame"]==60)
    candidate=next((p for p in observed["people"] if p["detection_id"]==0),None)
    source_box=read_json(ROOT/"runs/X-18/detections.json")["rows"][60]["people"][0][:4]
    result["post_run_model_conflict"]={"video":"X-18","frame":60,"t":6,"detection_id":0,"assistant_visual_label":"direct","selection":"post-run diagnosis of an observed model error; excluded from the fixed 24-frame table","model_observation":candidate,"input_detection_removed":any(r["detection_id"]==0 for r in videos["X-18"]["decisions"][60]["removed"]),"after_covered":{name:any(iou(t["box"],source_box)>=.5 for t in videos["X-18"][f"{name}_after"][60]["tracks"]) for name in ["bytetrack","botsort_reid"]}}
    write_json(ROOT/"runs/reflections/evaluation.json",result)
    for row in summaries: print(row,flush=True)


if __name__=="__main__": main()
