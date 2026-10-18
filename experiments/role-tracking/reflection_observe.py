"""Classify visible detections without manual zones or evaluation annotations."""
import argparse
import json
import time
from pathlib import Path

import torch
from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration

from common import ROOT, config, read_json, sampled_frames, sha256, write_json
from roles import annotate

PROMPT = """Inspect this bank-office camera frame for PHYSICAL people versus MIRROR/GLASS REFLECTIONS.
Yellow D<number> labels address detector boxes; a box is not proof of a real person.
Classify EVERY labelled box: direct = a physical person, including a real person seen THROUGH transparent glass or an open doorway; reflection = a reflected image of another person in a mirror or glass pane; uncertain = ambiguous, duplicate/partial box, object, insufficient evidence.
Being on glass or in the background does NOT prove reflection. A real person can walk through the glass doorway. Clothing, size and low contrast alone do not prove reflection.
For reflection identify the D id of the simultaneously visible DIRECT person whose reflected image this is. Only use reflection when BOTH the reflective surface and the corresponding direct person are visibly supported; otherwise use uncertain. Never identify a real person as their reflection solely because they are behind glass. Overlapping boxes around the SAME physical body are duplicates, not reflections.
Return JSON only: {"people":[{"id":0,"kind":"direct|reflection|uncertain","counterpart":null,"surface":false,"evidence":"at most 10 words of visible evidence"}]}.
For reflection, counterpart is another valid D number and surface is true. For direct/uncertain counterpart is null. No roles, face identification or violation analysis."""


def parse(raw, valid):
    try:
        obj=json.loads(raw[raw.index("{"):raw.rindex("}")+1])
        if not isinstance(obj,dict) or not isinstance(obj.get("people"),list):
            return [],"invalid_schema"
    except (ValueError,TypeError):
        return [],"invalid_json"
    parsed={}
    duplicates=set()
    for v in obj["people"]:
        if not isinstance(v,dict): continue
        idx=v.get("id")
        if type(idx) is not int or idx not in valid: continue
        if idx in parsed: duplicates.add(idx)
        kind=v.get("kind")
        partner=v.get("counterpart")
        if kind not in {"direct","reflection","uncertain"}: kind="uncertain"
        if kind=="reflection" and (type(partner) is not int or partner not in valid or partner==idx or v.get("surface") is not True):
            kind="uncertain"
        parsed[idx]={"detection_id":idx,"kind":kind,"counterpart":partner if kind=="reflection" else None,"surface":v.get("surface") is True,"evidence":str(v.get("evidence",""))}
    for idx in duplicates:
        parsed[idx]={"detection_id":idx,"kind":"uncertain","counterpart":None,"surface":False,"evidence":"duplicate model response"}
    for idx in valid:
        parsed.setdefault(idx,{"detection_id":idx,"kind":"uncertain","counterpart":None,"surface":False,"evidence":"missing model response"})
    for v in parsed.values():
        if v["kind"]=="reflection" and parsed[v["counterpart"]]["kind"]!="direct":
            v.update(kind="uncertain",counterpart=None)
    return list(parsed.values()),None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--videos",nargs="+")
    parser.add_argument("--output-root",type=Path,default=ROOT/"runs/reflections")
    args=parser.parse_args()
    cfg=config()
    policy=read_json(ROOT/"reflection_config.json")
    torch.manual_seed(cfg["seed"])
    torch.set_num_threads(4)
    processor=AutoProcessor.from_pretrained(cfg["role_model"],revision=cfg["role_revision"])
    model=Qwen3_5ForConditionalGeneration.from_pretrained(cfg["role_model"],revision=cfg["role_revision"],dtype=torch.bfloat16,device_map={"":"cuda:0"},attn_implementation="sdpa").eval()
    for vid in args.videos or cfg["videos"]:
        source=ROOT/"runs"/vid
        out=args.output_root/vid
        out.mkdir(parents=True,exist_ok=True)
        cached=read_json(source/"detections.json")
        tracks=read_json(source/"bytetrack.json")["rows"]
        meta={"model":cfg["role_model"],"revision":cfg["role_revision"],"prompt":PROMPT,"policy_config":policy,"detections_sha256":sha256(source/"detections.json"),"proposal_tracks_sha256":sha256(source/"bytetrack.json"),"provenance":"automatic predictions, no evaluation labels or manual masks"}
        target=out/"observations.json"
        previous=read_json(target) if target.exists() else None
        if previous and any(previous.get(k)!=v for k,v in meta.items()):
            raise ValueError("Reflection cache configuration mismatch")
        observations=previous["observations"] if previous else []
        seen={r["frame"] for r in observations}
        every=round(policy["sampling_seconds"]*cached["fps"])
        frames=set(range(0,len(cached["rows"]),every))|{len(cached["rows"])-1}
        for idx,t,image in sampled_frames(ROOT/"data"/f"{vid}.mov",cached["fps"]):
            if idx not in frames or idx in seen: continue
            row=cached["rows"][idx]
            active={tr["det_idx"] for tr in tracks[idx]["tracks"]}
            shown=[[*d[:4],1.0 if i in active or d[4]>=cfg["high_score"] else 0.0,d[5]] for i,d in enumerate(row["people"])]
            annotated,valid=annotate(image,shown,.5)
            (out/"observed_frames").mkdir(exist_ok=True)
            annotated.save(out/"observed_frames"/f"{idx:06d}.jpg",quality=95)
            raw,error,people,elapsed="",None,[],0.0
            if valid:
                messages=[{"role":"user","content":[{"type":"image","image":annotated},{"type":"text","text":PROMPT}]}]
                text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                inputs=processor(text=[text],images=[annotated],return_tensors="pt").to("cuda")
                start=time.perf_counter()
                with torch.inference_mode():
                    generated=model.generate(**inputs,max_new_tokens=512,do_sample=False)
                raw=processor.batch_decode(generated[:,inputs["input_ids"].shape[1]:],skip_special_tokens=True)[0]
                elapsed=time.perf_counter()-start
                people,error=parse(raw,valid)
                del inputs,generated
            observations.append({"frame":idx,"t":t,"valid_ids":valid,"people":people,"raw":raw,"seconds":elapsed,"parse_error":error})
            write_json(target,{**meta,"observations":observations})
            print(vid,t,[(p["detection_id"],p["kind"],p["counterpart"]) for p in people],error,round(elapsed,2),flush=True)


if __name__=="__main__": main()
