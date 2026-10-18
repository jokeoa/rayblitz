"""Tracker-independent role observations using local Qwen; these are NOT labels."""
import argparse
import gc
import json
import time

import cv2
import torch
from PIL import Image, ImageDraw
from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration

from common import ROOT, config, read_json, sampled_frames, sampled_frame_path, sha256, write_json

PROMPT = """Analyze this actual bank office camera image. Each detected person has a yellow rectangle labelled D<number>.
For EACH labelled person return their OBSERVABLE service role, not their identity or employment status.
Roles: banker = person operating the employee workstation/equipment and serving visitors;
customer = visitor being served across the desk; other = visible background person/reflection outside the service interaction;
unknown = insufficient visual evidence, ambiguous rectangle, or unclear role.
Do not assume the employee is on the left/right or closer to the camera. Do not infer roles from gender, clothing or age.
Use workstation orientation, desk sides, and visible interactions. There may be multiple people of any role.
Do not report any violation. An uncertain person MUST be unknown.
Return only JSON: {"people":[{"detection_id":0,"role":"banker|customer|other|unknown","evidence":"short visible reason"}]}.
Include only the labelled D IDs. Describe uncertainty honestly."""


def annotate(image, people, cutoff):
    img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img)
    valid = []
    for i, row in enumerate(people):
        if row[4] < cutoff:
            continue
        box = [round(x) for x in row[:4]]
        draw.rectangle(box, outline="yellow", width=2)
        x,y=box[:2]
        draw.rectangle((x,max(0,y-22),x+55,max(0,y-22)+22),fill="black")
        draw.text((x+4,max(0,y-22)+2),f"D{i}",fill="yellow",font_size=18)
        valid.append(i)
    return img,valid


def parse_result(text, valid):
    # Strict extraction; malformed/omitted labels remain unknown, never guessed.
    start,end=text.find("{"),text.rfind("}")
    if start<0 or end<start:
        return [],"missing_json"
    try:
        result=json.loads(text[start:end+1])
    except json.JSONDecodeError:
        return [],"invalid_json"
    if not isinstance(result,dict):
        return [],"invalid_root"
    people=result.get("people",[])
    if not isinstance(people,list):
        return [],"invalid_people"
    parsed=[]
    for value in people:
        if not isinstance(value,dict): continue
        idx=value.get("detection_id")
        role=value.get("role")
        if idx in valid and role in {"banker","customer","other","unknown"}:
            parsed.append({"detection_id":idx,"role":role,"evidence":str(value.get("evidence",""))})
    return parsed,None


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--videos",nargs="+")
    args=p.parse_args()
    cfg=config()
    torch.manual_seed(cfg["seed"])
    torch.set_num_threads(4)
    processor=AutoProcessor.from_pretrained(cfg["role_model"],revision=cfg["role_revision"])
    model=Qwen3_5ForConditionalGeneration.from_pretrained(cfg["role_model"],revision=cfg["role_revision"],dtype=torch.bfloat16,device_map={"":"cuda:0"},attn_implementation="sdpa").eval()
    for vid in args.videos or cfg["videos"]:
        directory=ROOT/"runs"/vid
        cached=read_json(directory/"detections.json")
        cache_hash=sha256(directory/"detections.json")
        target=directory/"role_observations.json"
        previous=read_json(target) if target.exists() else None
        if previous and (previous["prompt"]!=PROMPT or previous["model"]!=cfg["role_model"] or previous["revision"]!=cfg["role_revision"] or previous["detections_sha256"]!=cache_hash or previous["sampling_seconds"]!=cfg["role_interval_seconds"]):
            raise ValueError("Role cache belongs to different inputs, model, prompt, or sampling")
        observations=previous["observations"] if previous else []
        seen={row["frame"] for row in observations}
        every=round(cfg["role_interval_seconds"]*cfg["fps"])
        for idx,t,image in sampled_frames(ROOT/"data"/f"{vid}.mov",cfg["fps"]):
            if idx%every or idx in seen:
                continue
            annotated,valid=annotate(image,cached["rows"][idx]["people"],cfg["high_score"])
            saved=sampled_frame_path(vid,idx)
            saved.parent.mkdir(parents=True,exist_ok=True)
            annotated.save(saved,quality=95)
            if not valid:
                observations.append({"frame":idx,"t":t,"people":[],"raw":"","seconds":0,"parse_error":None})
            else:
                content=[{"type":"image","image":annotated},{"type":"text","text":PROMPT}]
                messages=[{"role":"user","content":content}]
                text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                inputs=processor(text=[text],images=[annotated],return_tensors="pt").to("cuda")
                start=time.perf_counter()
                with torch.inference_mode():
                    generated=model.generate(**inputs,max_new_tokens=384,do_sample=False)
                raw=processor.batch_decode(generated[:,inputs["input_ids"].shape[1]:],skip_special_tokens=True)[0]
                people,error=parse_result(raw,valid)
                observations.append({"frame":idx,"t":t,"people":people,"raw":raw,"seconds":time.perf_counter()-start,"parse_error":error})
                del inputs,generated
            write_json(target,{"model":cfg["role_model"],"revision":cfg["role_revision"],"dtype":"bfloat16","prompt":PROMPT,"detections_sha256":cache_hash,"sampling_seconds":cfg["role_interval_seconds"],"provenance":"automatic model predictions, not ground truth","observations":observations})
            print(vid,t,[(v["detection_id"],v["role"]) for v in observations[-1]["people"]],flush=True)
        gc.collect()
        torch.cuda.empty_cache()


if __name__=="__main__":
    main()
