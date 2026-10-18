"""Cache identical native-frame RT-DETR detections for both tracker arms."""
import argparse
import importlib.metadata
import time
from pathlib import Path

import cv2
import torch
from PIL import Image
from torchvision.ops import nms
from transformers import AutoImageProcessor, AutoModelForObjectDetection

from common import ROOT, config, sampled_frames, sha256, video_info, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos", nargs="+")
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--output-root", type=Path, default=ROOT / "runs")
    args = parser.parse_args()
    cfg = config()
    torch.manual_seed(cfg["seed"])
    torch.set_num_threads(4)
    processor = AutoImageProcessor.from_pretrained(cfg["detector"],revision=cfg["detector_revision"])
    model = AutoModelForObjectDetection.from_pretrained(cfg["detector"],revision=cfg["detector_revision"]).to("cuda").eval()
    person_class = next(int(k) for k,v in model.config.id2label.items() if v == "person")
    laptop_class = next(int(k) for k,v in model.config.id2label.items() if v == "laptop")
    provenance = {
        "config": cfg, "detector_revision": cfg["detector_revision"],
        "torch": torch.__version__, "transformers": importlib.metadata.version("transformers"),
        "gpu": torch.cuda.get_device_name(0), "input": "original resolution, ffmpeg fps filter",
    }
    write_json(args.output_root / "environment.json", provenance)
    for vid in args.videos or cfg["videos"]:
        path = ROOT / "data" / f"{vid}.mov"
        out = args.output_root / vid
        out.mkdir(parents=True, exist_ok=True)
        rows, batch = [], []
        start = time.perf_counter()

        def process_batch():
            images = [Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)) for _,_,image in batch]
            inputs = processor(images=images, return_tensors="pt").to("cuda")
            with torch.inference_mode():
                outputs = model(**inputs)
            sizes = torch.tensor([[im.height,im.width] for im in images], device="cuda")
            predictions = processor.post_process_object_detection(outputs, target_sizes=sizes, threshold=cfg["detector_score"])
            for (idx,t,img), pred in zip(batch,predictions):
                people, laptops = [], []
                for cls, dest in [(person_class,people),(laptop_class,laptops)]:
                    mask = pred["labels"] == cls
                    boxes, scores = pred["boxes"][mask], pred["scores"][mask]
                    keep = nms(boxes,scores,cfg["nms_iou"])
                    for j in keep.tolist():
                        b = boxes[j].cpu().tolist()
                        b[0],b[2] = max(0,b[0]),min(img.shape[1],b[2])
                        b[1],b[3] = max(0,b[1]),min(img.shape[0],b[3])
                        if b[2]>b[0] and b[3]>b[1]:
                            dest.append([round(x,3) for x in b]+[round(float(scores[j]),6),0])
                rows.append({"frame":idx,"t":t,"people":people,"laptops":laptops})
            batch.clear()

        for item in sampled_frames(path,cfg["fps"]):
            batch.append(item)
            if len(batch)==args.batch:
                process_batch()
        if batch:
            process_batch()
        torch.cuda.synchronize()
        elapsed = time.perf_counter()-start
        write_json(out / "detections.json", {"source_sha256":sha256(path),"info":video_info(path),"fps":cfg["fps"],"rows":rows,"decode_and_detect_seconds":elapsed})
        print(f"{vid}: {len(rows)} frames, {elapsed:.2f}s",flush=True)


if __name__ == "__main__":
    main()
