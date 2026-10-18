"""Export source frames and detector proposals for human role/timeline review.

Detection labels are local to each frame, never persistent person identities.
Human answers belong in a separate labels file; this script does not infer roles.
"""
from PIL import Image, ImageDraw

from common import ROOT, read_json, sampled_frames, sha256, write_json


CASES = [
    ("A", "X-4", [0, 10, 20, 65]),
    ("B", "X-18", [0, 8, 13.7, 20]),
    ("C", "X-48", [0, 10, 60, 68]),
]


def main():
    out = ROOT / "runs" / "first-entrant-review" / "batch-1"
    out.mkdir(parents=True, exist_ok=True)
    requests = []
    for prefix, video, times in CASES:
        source = ROOT / "data" / f"{video}.mov"
        cache = ROOT / "runs" / video / "detections.json"
        detections = read_json(cache)
        digest = sha256(source)
        if digest != detections["source_sha256"]:
            raise ValueError(f"Source hash mismatch: {video}")
        indices = {round(t * detections["fps"]): n for n, t in enumerate(times)}
        width, height = detections["info"]["width"], detections["info"]["height"]
        header, gutter = 60, 12
        sheet = Image.new("RGB", (width * 2 + gutter, (height + header) * 2 + gutter), "#17212b")
        for index, timestamp, frame in sampled_frames(source, detections["fps"]):
            if index not in indices:
                continue
            n = indices[index]
            review_id = f"{prefix}{n + 1}"
            row = detections["rows"][index]
            if row["frame"] != index or abs(row["t"] - timestamp) > 1e-6:
                raise ValueError(f"Sampling mismatch: {video}/{index}")
            image = Image.fromarray(frame[:, :, ::-1])
            image.save(out / f"{review_id}-source.png")
            draw = ImageDraw.Draw(image)
            boxes = []
            label_rects = []
            for detection_id, person in enumerate(row["people"]):
                if person[4] < 0.5:
                    continue
                box = person[:4]
                draw.rectangle(box, outline="#ffcf48", width=3)
                x = max(0, min(width - 64, round(box[0])))
                y = max(0, round(box[1]) - 31)
                while any(x < right and x + 64 > left and y < bottom and y + 31 > top
                          for left, top, right, bottom in label_rects):
                    y += 32
                label_rects.append((x, y, x + 64, y + 31))
                draw.rectangle((x, y, x + 63, y + 30), fill="#17212b")
                draw.text((x + 5, y + 3), f"D{detection_id}", fill="#ffcf48", font_size=24)
                boxes.append({"detection_id": detection_id, "box": box, "score": person[4]})
            card = Image.new("RGB", (width, height + header), "#17212b")
            card.paste(image, (0, header))
            text = ImageDraw.Draw(card)
            text.text((12, 6), f"{review_id}  |  {video}  |  {timestamp:.1f} s", fill="white", font_size=25)
            text.text((12, 36), "D labels apply to this frame only", fill="#c6d0da", font_size=16)
            card.save(out / f"{review_id}.png")
            sheet.paste(card, ((n % 2) * (width + gutter), (n // 2) * (height + header + gutter)))
            requests.append({"review_id": review_id, "video": video, "frame": index, "t": timestamp,
                             "source_sha256": digest, "detections_sha256": sha256(cache), "boxes": boxes,
                             "source_image": f"{review_id}-source.png", "marked_image": f"{review_id}.png"})
        if sum(r["video"] == video for r in requests) != len(times):
            raise ValueError(f"Missing requested source frames: {video}")
        sheet.save(out / f"{prefix}-{video}.jpg", quality=96)
        print(out / f"{prefix}-{video}.jpg", flush=True)
    write_json(out / "requests.json", {"purpose": "human review; no role labels inferred",
               "selection": "diagnostic cases including prior role errors and first-entrant counterexample; not holdout",
               "sampling": "canonical FFmpeg fps filter matching detection cache",
               "instructions": "Identify banker, customers, other people and reflections. D numbers are frame-local. Describe any missed person.",
               "frames": requests})


if __name__ == "__main__":
    main()
