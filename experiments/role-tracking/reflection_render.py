"""Before/after videos for BOTH trackers, with the original role observations."""
import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np

from common import ROOT,config,read_json,sampled_frames,write_json
from render import NAMES,label,panel,role_timeline


def titled_panel(image,row,name,title):
    out=panel(image,row,name)
    cv2.rectangle(out,(0,0),(out.shape[1],36),(24,24,24),-1)
    label(out,title,8,26,(245,245,245),.63)
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--videos",nargs="+")
    parser.add_argument("--output-root",type=Path,default=ROOT/"runs/reflections")
    args=parser.parse_args()
    cfg=config()
    for vid in args.videos or cfg["videos"]:
        src=ROOT/"runs"/vid;out=args.output_root/vid
        original=read_json(src/"detections.json")
        decisions=read_json(out/"decisions.json")["rows"]
        obs=read_json(src/"role_observations.json")["observations"]
        rows={}
        for name in NAMES:
            before=role_timeline(read_json(src/f"{name}.json")["rows"],obs,cfg)
            after=role_timeline(read_json(out/f"{name}.json")["rows"],obs,cfg)
            write_json(out/f"{name}_roles.json",{"observations":"unchanged original role observations; this experiment does not fix role reasoning","rows":after})
            rows[name]=(before,after)
        width,height=original["info"]["width"]*2,original["info"]["height"]+96
        writers={}
        for name in NAMES:
            target=out/f"{vid}-{name}-before-after.mp4"
            writers[name]=subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","bgr24","-s",f"{width}x{height}","-r",str(cfg["fps"]),"-i","-","-an","-c:v","libx264","-preset","fast","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart",str(target)],stdin=subprocess.PIPE)
        (out/"frames").mkdir(exist_ok=True)
        sample_frames={round(t*cfg["fps"]) for t in [0,2,4,5,6,10,15,18,19,20,21,23,25,30,36,40,50,55,60,65,70]}
        try:
            for idx,t,img in sampled_frames(ROOT/"data"/f"{vid}.mov",cfg["fps"]):
                for name in NAMES:
                    before,after=rows[name]
                    method="ByteTrack" if name=="bytetrack" else "BoT-SORT + ReID"
                    left=titled_panel(img,before[idx],name,f"BEFORE | {method}")
                    right=titled_panel(img,after[idx],name,f"AFTER | {method}")
                    for decision in decisions[idx]["removed"]:
                        di=decision["detection_id"]
                        x0,y0,x1,y1=map(round,original["rows"][idx]["people"][di][:4])
                        color=(100,100,245)
                        cv2.rectangle(right,(x0,y0+72),(x1,y1+72),color,1)
                        label(right,f"excluded D{di}",x0,y0+70,color,.39)
                    combined=np.concatenate([left,right],axis=1)
                    writers[name].stdin.write(combined.tobytes())
                    if idx in sample_frames and name=="bytetrack":
                        cv2.imwrite(str(out/"frames"/f"{idx:06d}.jpg"),combined)
        finally:
            for proc in writers.values(): proc.stdin.close()
        for proc in writers.values():
            if proc.wait()!=0: raise RuntimeError("Comparison video encoding failed")
        print(vid,"rendered both before/after comparisons",flush=True)


if __name__=="__main__": main()
