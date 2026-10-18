"""Run unmodified BoxMOT trackers on exactly the same cached detections."""
import argparse
import importlib.metadata
import time
from pathlib import Path

import numpy as np
import torch
from boxmot import BotSort, ByteTrack

from common import ROOT, config, overlap_fraction, read_json, sampled_frames, sha256, write_json


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--videos",nargs="+")
    p.add_argument("--run-dir",type=Path,default=ROOT/"runs")
    args=p.parse_args()
    cfg=config()
    torch.manual_seed(cfg["seed"])
    torch.set_num_threads(4)
    # BoxMOT 25.0.0 scales track_buffer by frame_rate/30.
    buffer_at_30fps=round(cfg["lost_seconds"]*30)
    for vid in args.videos or cfg["videos"]:
        directory=args.run_dir/vid
        cached=read_json(directory/"detections.json")
        path=ROOT/"data"/f"{vid}.mov"
        if sha256(path)!=cached["source_sha256"] or cached["fps"]!=cfg["fps"]:
            raise ValueError("Detection cache does not match input/configuration")
        trackers={
            "bytetrack":ByteTrack(min_conf=cfg["detector_score"],track_thresh=cfg["high_score"],match_thresh=.8,track_buffer=buffer_at_30fps,frame_rate=cfg["fps"]),
            "botsort_reid":BotSort(track_high_thresh=cfg["high_score"],track_low_thresh=cfg["detector_score"],new_track_thresh=cfg["new_track_score"],track_buffer=buffer_at_30fps,frame_rate=cfg["fps"],match_thresh=.8,use_cmc=False,use_embeddings=True,reid_weights=ROOT/"weights"/cfg["reid"],device="cuda:0",half=False,det_thresh=cfg["detector_score"]),
        }
        rows={name:[] for name in trackers}
        timings={name:[] for name in trackers}
        for idx,t,image in sampled_frames(path,cfg["fps"]):
            entry=cached["rows"][idx]
            if idx!=entry["frame"]:
                raise ValueError("Frame cache index mismatch")
            dets=np.asarray(entry["people"],dtype=np.float32).reshape(-1,6)
            for name,tracker in trackers.items():
                torch.cuda.synchronize()
                start=time.perf_counter()
                result=tracker.update(dets.copy(),image)
                torch.cuda.synchronize()
                timings[name].append(time.perf_counter()-start)
                output=[]
                for r in result:
                    box=r[:4].tolist()
                    det_idx=int(r[7])
                    overlaps=max((overlap_fraction(box,d[:4]) for j,d in enumerate(dets) if j!=det_idx and d[4]>=cfg["high_score"]),default=0)
                    source_idx=entry.get("source_detection_indices",range(len(dets)))[det_idx]
                    output.append({"id":int(r[4]),"box":box,"score":float(r[5]),"det_idx":source_idx,"overlap":round(overlaps,3)})
                rows[name].append({"frame":idx,"t":t,"tracks":output})
        for name,output in rows.items():
            totals={"tracker_update_seconds_including_first_load":sum(timings[name]),"steady_update_ms_median":float(np.median(timings[name][1:])*1000),"steady_update_ms_p95":float(np.percentile(timings[name][1:],95)*1000)}
            tracker=trackers[name]
            provenance={"max_time_lost_frames":tracker.max_time_lost,"use_embeddings":getattr(tracker,"use_embeddings",False),"use_cmc":getattr(tracker,"use_cmc",False)}
            if name=="botsort_reid":
                provenance["reid_weights_sha256"]=sha256(ROOT/"weights"/cfg["reid"])
            write_json(directory/f"{name}.json",{"tracker":name,"boxmot":importlib.metadata.version("boxmot"),"config":cfg,"resolved":provenance,"detections_sha256":sha256(directory/"detections.json"),"timing":totals,"rows":output})
            print(vid,name,totals,"ids",sorted({x["id"] for row in output for x in row["tracks"]}),flush=True)
        del trackers
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
