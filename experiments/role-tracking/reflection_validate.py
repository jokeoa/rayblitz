"""Verify provenance, exact removal, source-index mapping and rendered videos."""
import argparse
import json
import subprocess
from pathlib import Path

from common import ROOT,config,read_json,sha256,write_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--videos",nargs="+")
    parser.add_argument("--output-root",type=Path,default=ROOT/"runs/reflections")
    args=parser.parse_args()
    out=args.output_root
    result={"checks":[],"videos":[]}
    for vid in args.videos or config()["videos"]:
        src=ROOT/"runs"/vid;dst=out/vid
        original=read_json(src/"detections.json")
        filtered=read_json(dst/"detections.json")
        decisions=read_json(dst/"decisions.json")["rows"]
        assert filtered["source_detections_sha256"]==sha256(src/"detections.json")
        assert filtered["source_sha256"]==sha256(ROOT/"data"/f"{vid}.mov")
        assert len(filtered["rows"])==len(original["rows"])==len(decisions)
        for old,new,decision in zip(original["rows"],filtered["rows"],decisions):
            removed={x["detection_id"] for x in decision["removed"]}
            expected=[i for i in range(len(old["people"])) if i not in removed]
            assert new["source_detection_indices"]==expected
            assert new["people"]==[old["people"][i] for i in expected]
            assert (old["frame"],old["t"])==(new["frame"],new["t"])==(decision["frame"],decision["t"])
        for name in ["bytetrack","botsort_reid"]:
            tracks=read_json(dst/f"{name}.json")
            assert tracks["detections_sha256"]==sha256(dst/"detections.json")
            assert len(tracks["rows"])==len(filtered["rows"])
            for detection,tr in zip(filtered["rows"],tracks["rows"]):
                allowed=set(detection["source_detection_indices"])
                assert all(x["det_idx"] in allowed for x in tr["tracks"])
            path=dst/f"{vid}-{name}-before-after.mp4"
            meta=json.loads(subprocess.check_output(["ffprobe","-v","error","-count_frames","-select_streams","v:0","-show_entries","stream=codec_name,width,height,nb_read_frames:format=duration","-of","json",str(path)]))
            stream=meta["streams"][0]
            assert int(stream["nb_read_frames"])==len(original["rows"])
            assert stream["width"]==original["info"]["width"]*2
            assert stream["height"]==original["info"]["height"]+96
            assert abs(float(meta["format"]["duration"])-len(original["rows"])/original["fps"])<.05
            result["videos"].append({"video":vid,"tracker":name,**stream,"duration":meta["format"]["duration"]})
    result["checks"]=["Source video and common detection hashes match","Filtered rows are exact subsets; no box/score edits","All tracker detection indices refer to retained original boxes",f"All {len(result['videos'])} comparison MP4s fully decoded with expected dimensions, frame counts and durations"]
    result["quality_warning"]="These checks verify execution, not classifier accuracy. See the separately labelled evaluation."
    write_json(out/"validation.json",result)
    print(result)


if __name__=="__main__": main()
