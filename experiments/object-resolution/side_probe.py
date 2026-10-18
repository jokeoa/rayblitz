"""Additional source frames for people orientation; counter positions use cached frames."""
import subprocess
from pathlib import Path
from PIL import Image
from common import ROOT, read_json, sha256, write_json
from desk_scope import in_desk_region
from owl import Detector

CASES = [("X-24",2),("X-24",4),("X-24",6),("X-24",12),
         ("X-1",4),("X-1",10),("X-1",16),("X-1",24),
         ("X-40",8),("X-14",30)]


def main():
    out = ROOT/"runs/side-probe"
    out.mkdir(exist_ok=False)
    manifest = read_json(ROOT/"runs/manifest.json")
    scope = read_json(ROOT/"runs/desk-scope.json")
    episodes = {e["video"]:e for e in manifest["episodes"]}
    detector = Detector(manifest["config"])
    rows = []
    for video,t in CASES:
        source = Path("/home/ubuntu/role-tracking-prototype/data")/f"{video}.mov"
        if sha256(source) != episodes[video]["source_sha256"]:
            raise ValueError("Side frame video differs")
        path = out/f"{video}-{t}.png"
        subprocess.run(["ffmpeg","-v","error","-ss",str(t),"-i",str(source),"-frames:v","1",str(path)],check=True)
        image = Image.open(path).convert("RGB")
        desk = scope["videos"][video]
        predictions, seconds = detector.predict([image.crop(desk["crop"])],[desk["crop"]])
        rows.append({"video":video,"t":t,"source_sha256":episodes[video]["source_sha256"],
            "image":str(path.relative_to(ROOT/"runs")),"image_sha256":sha256(path),
            "desk":desk,"predictions":[p for p in detector.merge(predictions) if in_desk_region(p,desk)],"seconds":seconds})
        write_json(out/"results.json",rows)
    write_json(out/"metadata.json",{"code_sha256":sha256(ROOT/"side_probe.py"),"config_sha256":manifest["config_sha256"],
        "scope_sha256":sha256(ROOT/"runs/desk-scope.json"),"selection":"front/back people diagnostics, separate from fixed benchmark episodes"})
    (out/"side_probe.py").write_bytes((ROOT/"side_probe.py").read_bytes())
    write_json(out/"status.json",{"status":"complete","count":len(rows)})


if __name__ == "__main__":
    main()
