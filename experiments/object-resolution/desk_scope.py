"""Consume the project's reviewed desk reference without inventing geometry."""
import math
from pathlib import Path

from common import ROOT, read_json, sha256, write_json


def in_desk_region(prediction, desk):
    """A 2-D candidate gate, not evidence of contact with the surface."""
    if prediction["class"] == "safe":
        return False
    x0, y0, x1, y1 = prediction["box"]
    left, top, right, bottom = desk["box"]
    return left <= (x0 + x1) / 2 <= right and top <= y1 <= bottom


def main():
    authority = ROOT.parent / "role-tracking" / "scene_references.json"
    references = read_json(authority)
    manifest = read_json(ROOT / "runs/manifest.json")
    result = {"authority": str(authority), "authority_sha256": sha256(authority),
              "manifest_sha256": sha256(ROOT / "runs/manifest.json"),
              "rule": "bottom center inside reviewed desk bounding box; safe excluded",
              "limitation": "Region membership does not establish on-table contact. Hands and held objects can project into it. Evaluation references include only visually reviewed objects resting on the desk.",
              "crop_rule": "square centered on desk, side 1.2 times longest desk dimension, clipped to image",
              "videos": {}, "excluded": []}
    for episode in manifest["episodes"]:
        video = episode["video"]
        if video not in references["videos"]:
            result["excluded"].append({"video": video, "reason": "no reviewed scene reference"})
            continue
        ref = references["videos"][video]
        if ref["source_sha256"] != episode["source_sha256"] or ref["image_size"] != episode["size"]:
            raise ValueError(f"{video}: source/view differs from reviewed geometry")
        desk = ref["objects"]["desk"]
        if desk is None:
            raise ValueError(f"{video}: reviewed desk missing")
        image_path = (authority.parent / desk["image"]).resolve()
        if not image_path.is_relative_to(authority.parent.resolve()) or sha256(image_path) != desk["image_sha256"]:
            raise ValueError(f"{video}: desk reference image differs")
        x0, y0, x1, y1 = desk["box"]
        w, h = episode["size"]
        if not 0 <= x0 < x1 <= w or not 0 <= y0 < y1 <= h:
            raise ValueError(f"{video}: invalid desk coordinates")
        cx, cy, side = (x0 + x1) / 2, (y0 + y1) / 2, max(x1-x0, y1-y0) * 1.2
        crop = [max(0, math.floor(cx-side/2)), max(0, math.floor(cy-side/2)),
                min(w, math.ceil(cx+side/2)), min(h, math.ceil(cy+side/2))]
        result["videos"][video] = {**desk, "crop": crop, "source_sha256": ref["source_sha256"]}
    write_json(ROOT / "runs/desk-scope.json", result)
    print(len(result["videos"]), "desk references; excluded", result["excluded"])


if __name__ == "__main__":
    main()
