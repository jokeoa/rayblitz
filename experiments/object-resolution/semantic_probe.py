"""Bounded local VLM check of detector proposals, with no reference-label input."""
import base64
import io
import json
import time
import urllib.request

from PIL import Image, ImageDraw
from common import ROOT, iou, read_json, sha256, write_json

PROMPT = '''Classify only the object outlined in cyan. The image is a crop from a workplace video. Ignore other objects. Choose one label: cash (a stack or bundle of banknotes), packaging (an empty banknote wrapper or strap), card (a plastic bank/payment/ID card), document (paper document), other, unknown. Use unknown when the visible pixels cannot distinguish the categories. Do not assume that rectangular objects are cash. Output JSON only: {"label":"...","visible_evidence":"brief visual evidence"}.'''


def main():
    root = ROOT/"runs"
    out = root/"semantic-probe"
    out.mkdir(exist_ok=False)
    manifest = read_json(root/"manifest.json")
    scope = read_json(root/"desk-scope.json")
    model = json.load(urllib.request.urlopen("http://127.0.0.1:8081/v1/models"))["data"][0]["id"]
    write_json(out/"metadata.json", {"prompt": PROMPT, "model": model, "temperature": 0,
        "frame": 20, "proposal_score": .15, "max_dimension": 96, "crop_side": 96,
        "image_size": 384, "resize": "LANCZOS; no new source detail", "code_sha256": sha256(ROOT/"semantic_probe.py"),
        "manifest_sha256": sha256(root/"manifest.json"),
        "note": "Development diagnostic. Labels not supplied to inference. Context is restricted to 96 source pixels around each candidate."})
    (out/"semantic_probe.py").write_bytes((ROOT/"semantic_probe.py").read_bytes())
    write_json(out/"status.json", {"status": "running"})
    results = []
    for ep in manifest["episodes"]:
        if ep["video"] not in scope["videos"]:
            continue
        path = root/ep["video"]/"desk-detections.json"
        row = read_json(path)["rows"][20]
        candidates = []
        for p in sorted(row["arms"]["desk"], key=lambda p:p["score"], reverse=True):
            if p["class"] not in {"cash", "card", "document", "packaging"} or p["score"] < .15:
                continue
            if max(p["box"][2]-p["box"][0], p["box"][3]-p["box"][1]) > 96:
                continue
            if not any(iou(p["box"], q["box"]) >= .6 for q in candidates):
                candidates.append(p)
        frame = ep["frames"][20]
        if sha256(root/frame["native"]) != frame["native_sha256"]:
            raise ValueError("Source frame changed")
        image = Image.open(root/frame["native"]).convert("RGB")
        for i, p in enumerate(candidates):
            x0,y0,x1,y1 = p["box"]
            cx,cy = (x0+x1)/2,(y0+y1)/2
            crop = [max(0,round(cx-48)),max(0,round(cy-48)),min(image.width,round(cx+48)),min(image.height,round(cy+48))]
            im = image.crop(crop).resize((384,384), Image.Resampling.LANCZOS)
            sx,sy = 384/(crop[2]-crop[0]),384/(crop[3]-crop[1])
            ImageDraw.Draw(im).rectangle([(x0-crop[0])*sx,(y0-crop[1])*sy,(x1-crop[0])*sx,(y1-crop[1])*sy],outline="cyan",width=2)
            buffer = io.BytesIO(); im.save(buffer,format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode()
            payload = {"model": model, "temperature": 0, "max_tokens": 160,
                       "chat_template_kwargs": {"enable_thinking": False},
                       "messages": [{"role":"user","content":[{"type":"text","text":PROMPT},
                       {"type":"image_url","image_url":{"url":"data:image/png;base64,"+encoded}}]}]}
            request = urllib.request.Request("http://127.0.0.1:8081/v1/chat/completions",
                data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
            tick = time.perf_counter()
            response = json.load(urllib.request.urlopen(request,timeout=120))
            text = response["choices"][0]["message"]["content"]
            try:
                parsed = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
                if parsed.get("label") not in {"cash","packaging","card","document","other","unknown"}:
                    parsed = None
            except (ValueError,AttributeError):
                parsed = None
            results.append({"video":ep["video"],"frame":20,"t":row["t"],"proposal":p,
                "crop":crop,"frame_sha256":frame["native_sha256"],"baseline_sha256":sha256(path),
                "source_sha256":ep["source_sha256"],"parsed":parsed,"response":response,
                "seconds":time.perf_counter()-tick})
            im.save(out/f"{ep['video']}-{i}.png")
            write_json(out/"results.json",results)
            print(ep["video"],i,parsed,flush=True)
    write_json(out/"status.json",{"status":"complete","count":len(results)})


if __name__ == "__main__":
    main()
