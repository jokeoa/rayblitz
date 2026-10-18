"""Conservative offline reflection gate; never reads annotation/role files."""
import argparse
from collections import Counter
from math import hypot
from pathlib import Path

from common import ROOT, config, overlap_fraction, read_json, sha256, write_json


def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/max(union,1)


def continuous(a,b,cfg):
    step=hypot((a[0]+a[2]-b[0]-b[2])/2,(a[1]+a[3]-b[1]-b[3])/2)
    size=max(hypot(a[2]-a[0],a[3]-a[1]),1)
    return iou(a,b)>=cfg["min_step_iou"] or step/size<=cfg["max_normalized_step"]


def suppressions(detections,tracks,observations,cfg):
    """Returns source detection indices only; unknown/missing evidence is kept.

    Offline two-second lookahead plus a whole-clip direct-person veto. Any
    explicit direct classification protects that provisional identity globally.
    This is an experimental safety constraint, not a correctness guarantee.
    """
    by_id=[{t["id"]:t for t in row["tracks"]} for row in tracks]
    by_det=[]
    for row in tracks:
        groups={}
        for tr in row["tracks"]: groups.setdefault(tr["det_idx"],[]).append(tr["id"])
        by_det.append({d:ids[0] for d,ids in groups.items() if len(ids)==1})
    protected=set()
    evidence=[]
    for obs in sorted(observations,key=lambda o:o["frame"]):
        f=obs["frame"]
        classified={p["detection_id"]:p for p in obs["people"]}
        pairs={}
        for d,p in classified.items():
            tid=by_det[f].get(d)
            if tid is None: continue
            if p["kind"]=="direct": protected.add(tid)
            partner=p.get("counterpart")
            if p["kind"]=="reflection" and p.get("surface") is True and classified.get(partner,{}).get("kind")=="direct":
                pid=by_det[f].get(partner)
                if pid is not None and pid!=tid: pairs[tid]=pid
        evidence.append({"frame":f,"t":obs["t"],"pairs":pairs})
    removed=[{} for _ in detections]
    intervals=[]
    rejected=Counter()
    for left,right in zip(evidence,evidence[1:]):
        if right["t"]-left["t"]>cfg["max_interval_seconds"]: continue
        for tid,pid in left["pairs"].items():
            if right["pairs"].get(tid)!=pid: continue
            if tid in protected:
                rejected["direct_observation_elsewhere"]+=1
                continue
            last_pair=None
            pending=[]
            failure=None
            for f in range(left["frame"],right["frame"]+1):
                tr,partner=by_id[f].get(tid),by_id[f].get(pid)
                if tr is None or partner is None:
                    failure="missing_track_or_counterpart";break
                di,pi=tr["det_idx"],partner["det_idx"]
                if di==pi or by_det[f].get(di)!=tid or by_det[f].get(pi)!=pid:
                    failure="ambiguous_detection_association";break
                a,b=detections[f]["people"][di][:4],detections[f]["people"][pi][:4]
                if overlap_fraction(a,b)>=cfg["max_pair_overlap"]:
                    failure="overlapping_physical_bodies";break
                if last_pair and (not continuous(last_pair[0],a,cfg) or not continuous(last_pair[1],b,cfg)):
                    failure="abrupt_track_motion";break
                last_pair=(a,b)
                pending.append((f,di))
            if failure:
                rejected[failure]+=1
                continue
            interval={"start_frame":left["frame"],"end_frame":right["frame"],"reflection_track_id":tid,"direct_track_id":pid}
            intervals.append(interval)
            for f,di in pending: removed[f][di]=interval
    return removed,{"protected_direct_track_ids":sorted(protected),"accepted_intervals":intervals,"rejected_interval_reasons":dict(rejected)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--videos",nargs="+")
    parser.add_argument("--output-root",type=Path,default=ROOT/"runs/reflections")
    args=parser.parse_args()
    cfg=read_json(ROOT/"reflection_config.json")
    summary=[]
    for vid in args.videos or config()["videos"]:
        source=ROOT/"runs"/vid
        out=args.output_root/vid
        base=read_json(source/"detections.json")
        tr=read_json(source/"bytetrack.json")
        obs=read_json(out/"observations.json")
        if obs["detections_sha256"]!=sha256(source/"detections.json") or obs["proposal_tracks_sha256"]!=sha256(source/"bytetrack.json"):
            raise ValueError("Reflection inputs changed")
        if obs["policy_config"]!=cfg: raise ValueError("Reflection policy changed since inference")
        every=round(cfg["sampling_seconds"]*base["fps"])
        expected=set(range(0,len(base["rows"]),every))|{len(base["rows"])-1}
        actual=[o["frame"] for o in obs["observations"]]
        if len(set(actual))!=len(actual) or set(actual)!=expected:
            raise ValueError("Reflection observation pass is incomplete or duplicated")
        removed,details=suppressions(base["rows"],tr["rows"],obs["observations"],cfg)
        rows=[]
        total=0
        for row,mask in zip(base["rows"],removed):
            keep=[i for i in range(len(row["people"])) if i not in mask]
            rows.append({**row,"people":[row["people"][i] for i in keep],"source_detection_indices":keep})
            total+=len(mask)
        write_json(out/"detections.json",{**base,"rows":rows,"filter":"reflection_v1","filter_config":cfg,"source_detections_sha256":sha256(source/"detections.json"),"reflection_observations_sha256":sha256(out/"observations.json")})
        write_json(out/"decisions.json",{"policy":cfg,**details,"rows":[{"frame":r["frame"],"t":r["t"],"removed":[{"detection_id":i,**proof} for i,proof in mask.items()]} for r,mask in zip(base["rows"],removed)]})
        stat={"video":vid,"suppressed_detection_samples":total,"accepted_intervals":len(details["accepted_intervals"]),"protected_direct_track_ids":details["protected_direct_track_ids"],"rejected_interval_reasons":details["rejected_interval_reasons"],"model_seconds":sum(o["seconds"] for o in obs["observations"]),"observations":len(obs["observations"]),"parse_errors":sum(o["parse_error"] is not None for o in obs["observations"])}
        summary.append(stat)
        print(stat,flush=True)
    write_json(args.output_root/"filter_summary.json",summary)


if __name__=="__main__": main()
