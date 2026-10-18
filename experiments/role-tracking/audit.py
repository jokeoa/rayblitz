"""Export fixed source-selected audit moments, plus candidate tracking discontinuities.

Candidates are diagnostics, not measured errors or ground truth.
"""
from collections import defaultdict

import cv2
import numpy as np

from common import ROOT, config, read_json, sampled_frames, write_json
from render import NAMES, panel


def candidates(rows, fps):
    last={}
    events=[]
    active_overlap=set()
    for row in rows:
        overlap_now=set()
        for tr in row["tracks"]:
            identity=tr["id"]
            if identity not in last:
                events.append({"kind":"first_visible_track","t":row["t"],"id":identity})
            elif row["frame"]-last[identity]>1:
                events.append({"kind":"track_resumed","t":row["t"],"id":identity,"gap_seconds":(row["frame"]-last[identity]-1)/fps})
            if tr["overlapping"]:
                overlap_now.add(identity)
                if identity not in active_overlap:
                    events.append({"kind":"box_overlap_started","t":row["t"],"id":identity})
            last[identity]=row["frame"]
        active_overlap=overlap_now
    return events


def main():
    cfg=config()
    cases=read_json(ROOT/"audit_cases.json")
    folder=ROOT/"runs/audit"
    folder.mkdir(parents=True,exist_ok=True)
    selected=defaultdict(dict)
    for case in cases:
        for t in case["times"]:
            selected[case["video"]][round(t*cfg["fps"])]=t
    all_candidates={}
    for vid,indices in selected.items():
        timelines={name:read_json(ROOT/"runs"/vid/f"{name}_roles.json")["rows"] for name in NAMES}
        all_candidates[vid]={name:candidates(rows,cfg["fps"]) for name,rows in timelines.items()}
        moments={}
        for idx,t,image in sampled_frames(ROOT/"data"/f"{vid}.mov",cfg["fps"]):
            if idx not in indices: continue
            result=np.concatenate([panel(image,timelines[name][idx],name) for name in NAMES],axis=1)
            cv2.imwrite(str(folder/f"{vid}-{idx:06d}.jpg"),result,[cv2.IMWRITE_JPEG_QUALITY,94])
            moments[idx]={name:timelines[name][idx]["tracks"] for name in NAMES}
        write_json(folder/f"{vid}-moments.json",moments)
        for case in (c for c in cases if c["video"]==vid):
            thumbs=[]
            for t in case["times"]:
                img=cv2.imread(str(folder/f"{vid}-{round(t*cfg['fps']):06d}.jpg"))
                thumbs.append(cv2.resize(img,(464,472)))
            rows=[]
            for offset in range(0,len(thumbs),3):
                group=thumbs[offset:offset+3]
                while len(group)<3: group.append(np.full_like(thumbs[0],24))
                rows.append(np.concatenate(group,axis=1))
            cv2.imwrite(str(folder/f"{vid}-{case['name']}.jpg"),np.concatenate(rows,axis=0),[cv2.IMWRITE_JPEG_QUALITY,94])
    write_json(folder/"candidates.json",all_candidates)
    print(f"Audit snapshots: {folder}")


if __name__=="__main__":
    main()
