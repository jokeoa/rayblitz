"""Hash decoded RGB pixels, independent of PNG encoder/version metadata."""
import hashlib
from PIL import Image
from common import ROOT, read_json, write_json

root = ROOT / "runs"
manifest = read_json(root / "manifest.json")
hashes = {}
for ep in manifest["episodes"]:
    for frame in ep["frames"]:
        for arm in ("native", "reduced"):
            with Image.open(root / frame[arm]) as image:
                hashes[frame[arm]] = hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()
write_json(root / "pixel-hashes.json", hashes)
print("RGB hashes saved:", len(hashes))
