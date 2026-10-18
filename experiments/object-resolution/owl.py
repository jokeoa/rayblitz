"""One frozen detector implementation for every resolution arm."""
import time

import torch
from torchvision.ops import batched_nms
from transformers import Owlv2ForObjectDetection, Owlv2Processor

from common import original_box


class Detector:
    def __init__(self, config, batch_size=2):
        self.config, self.batch_size = config, batch_size
        torch.manual_seed(config["seed"])
        torch.set_num_threads(4)
        self.processor = Owlv2Processor.from_pretrained(config["model"], revision=config["revision"], local_files_only=True)
        self.model = Owlv2ForObjectDetection.from_pretrained(config["model"], revision=config["revision"], local_files_only=True).to("cuda").eval()
        self.prompts = [x["prompt"] for x in config["classes"]]

    def predict(self, images, crops):
        predictions = []
        torch.cuda.synchronize()
        tick = time.perf_counter()
        for offset in range(0, len(images), self.batch_size):
            batch = images[offset:offset+self.batch_size]
            texts = [self.prompts] * len(batch)
            inputs = self.processor(text=texts, images=batch, return_tensors="pt").to("cuda")
            with torch.inference_mode():
                outputs = self.model(**inputs)
            sizes = torch.tensor([(im.height, im.width) for im in batch], device="cuda")
            results = self.processor.post_process_grounded_object_detection(
                outputs=outputs, target_sizes=sizes, threshold=self.config["candidate_score"], text_labels=texts)
            for k, result in enumerate(results):
                crop = crops[offset+k]
                for box, score, label in zip(result["boxes"].cpu().tolist(), result["scores"].cpu().tolist(), result["text_labels"]):
                    box = original_box(box, crop, batch[k].size)
                    if box[2] > box[0] and box[3] > box[1]:
                        index = self.prompts.index(label)
                        predictions.append({"box": box, "score": score, "class": self.config["classes"][index]["id"],
                                            "class_index": index, "crop": list(crop)})
        torch.cuda.synchronize()
        return predictions, time.perf_counter()-tick

    def merge(self, predictions):
        if not predictions:
            return []
        keep = batched_nms(torch.tensor([p["box"] for p in predictions]),
                           torch.tensor([p["score"] for p in predictions]),
                           torch.tensor([p["class_index"] for p in predictions]), self.config["nms_iou"])
        return [predictions[i] for i in keep.tolist()]
