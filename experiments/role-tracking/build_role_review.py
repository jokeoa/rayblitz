"""Package the review form and original frames into one offline HTML document."""
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    directory = ROOT / "runs" / "first-entrant-review" / "batch-1"
    manifest_path = directory / "requests.json"
    manifest = json.loads(manifest_path.read_text())
    batch_id = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    for frame in manifest["frames"]:
        image = (directory / frame["source_image"]).read_bytes()
        frame["image"] = "data:image/png;base64," + base64.b64encode(image).decode("ascii")
        # PNG IHDR dimensions: keep overlays in original source coordinates.
        if image[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Expected a PNG source frame")
        frame["width"] = int.from_bytes(image[16:20], "big")
        frame["height"] = int.from_bytes(image[20:24], "big")
    data = {"batch_id": batch_id, "title": "Наблюдения по видео · Батч 1", **manifest}
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    template = (ROOT / "role_review_form.html").read_text()
    if template.count("__REVIEW_DATA__") != 1:
        raise ValueError("Expected one data placeholder")
    target = directory / "index.html"
    target.write_text(template.replace("__REVIEW_DATA__", payload))
    print(f"{target} ({target.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
