"""Replay identical role observations onto each tracker and render diagnostics."""
import subprocess
from collections import Counter,deque

import cv2
import numpy as np

from common import ROOT, config, read_json, sampled_frames, write_json

NAMES=("bytetrack","botsort_reid")
COLORS={"banker":(70,210,80),"customer":(240,165,60),"other":(170,170,170),"unknown":(40,200,240)}


def role_timeline(tracks, observations, cfg):
    votes={r["frame"]:{v["detection_id"]:v for v in r["people"]} for r in observations}
    states={}
    output=[]
    for row in tracks:
        current=[]
        for tr in row["tracks"]:
            state=states.setdefault(tr["id"],{"last":row["t"],"votes":deque(maxlen=3),"role":"unknown","reason":"insufficient_votes"})
            gap=row["t"]-state["last"]
            if gap>cfg["role_reset_gap_seconds"]:
                state["votes"].clear()
                state["role"]="unknown"
                state["reason"]="recheck_after_gap"
            vote=votes.get(row["frame"],{}).get(tr["det_idx"])
            if vote and tr["overlap"]<cfg["overlap_fraction"]:
                new=vote["role"]
                if new!="unknown":
                    if state["votes"] and state["votes"][-1]!=new:
                        state["votes"].clear()
                        state["role"]="unknown"
                        state["reason"]="role_conflict"
                    state["votes"].append(new)
                    if len(state["votes"])>=cfg["role_min_votes"] and len(set(state["votes"]))==1:
                        state["role"]=new
                        state["reason"]="consistent_model_observations"
            state["last"]=row["t"]
            current.append({**tr,"role":state["role"],"role_reason":state["reason"],"role_votes":len(state["votes"]),"gap_seconds":round(gap,2),"overlapping":tr["overlap"]>=cfg["overlap_fraction"]})
        output.append({"frame":row["frame"],"t":row["t"],"tracks":current})
    return output


def label(img,text,x,y,color,scale=.55):
    (w,h),baseline=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,scale,1)
    y=max(h+5,min(img.shape[0]-baseline-2,y))
    x=max(0,min(img.shape[1]-w-3,x))
    cv2.rectangle(img,(x,y-h-5),(x+w+4,y+baseline+2),(15,15,20),-1)
    cv2.putText(img,text,(x+2,y-2),cv2.FONT_HERSHEY_SIMPLEX,scale,color,1,cv2.LINE_AA)


def panel(image,row,name):
    h,w=image.shape[:2]
    out=np.full((h+96,w,3),24,dtype=np.uint8)
    out[72:72+h]=image
    label(out,"ByteTrack" if name=="bytetrack" else "BoT-SORT + OSNet ReID",8,25,(245,245,245),.65)
    label(out,f't={row["t"]:.1f}s | frame {row["frame"]} | 10 fps',8,53,(200,200,200),.48)
    for tr in row["tracks"]:
        x0,y0,x1,y1=[round(v) for v in tr["box"]]
        color=COLORS[tr["role"]]
        cv2.rectangle(out,(x0,y0+72),(x1,y1+72),color,2)
        text=f'ID {tr["id"]} | {tr["role"]}'
        if tr["overlapping"]: text+=" | overlap?"
        label(out,text,x0,y0+70,color,.45)
    label(out,"Roles: automatic predictions; unknown = insufficient evidence",5,h+90,(210,210,210),.37)
    return out


def main():
    cfg=config()
    summaries=[]
    for vid in cfg["videos"]:
        directory=ROOT/"runs"/vid
        observed=read_json(directory/"role_observations.json")["observations"]
        timelines={}
        for name in NAMES:
            raw=read_json(directory/f"{name}.json")
            timelines[name]=role_timeline(raw["rows"],observed,cfg)
            write_json(directory/f"{name}_roles.json",{"role_policy":"causal votes; reset after gap>1s; contradictory vote resets role; no GT", "rows":timelines[name]})
            counts=Counter(tr["role"] for row in timelines[name] for tr in row["tracks"])
            ids=sorted({tr["id"] for row in timelines[name] for tr in row["tracks"]})
            summaries.append({"video":vid,"tracker":name,"track_ids":ids,"track_count":len(ids),"visible_track_samples":sum(counts.values()),"role_samples":dict(counts),"role_coverage":1-counts["unknown"]/max(sum(counts.values()),1),**raw["timing"]})
        info=read_json(directory/"detections.json")["info"]
        width,height=info["width"]*2,info["height"]+96
        target=directory/f"{vid}-comparison.mp4"
        proc=subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","bgr24","-s",f"{width}x{height}","-r",str(cfg["fps"]),"-i","-","-an","-c:v","libx264","-preset","fast","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart",str(target)],stdin=subprocess.PIPE)
        try:
            for idx,t,image in sampled_frames(ROOT/"data"/f"{vid}.mov",cfg["fps"]):
                panels=[panel(image,timelines[name][idx],name) for name in NAMES]
                proc.stdin.write(np.concatenate(panels,axis=1).tobytes())
        finally:
            proc.stdin.close()
        if proc.wait()!=0: raise RuntimeError("Video render failed")
        print(target,flush=True)
    write_json(ROOT/"runs/summary.json",summaries)


if __name__=="__main__":
    main()
