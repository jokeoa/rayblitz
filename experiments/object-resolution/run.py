"""Run the frozen comparison; retain source and explicit completion status."""
import shutil
import subprocess
import sys
import time

from common import ROOT, write_json

run = ROOT / "runs"
snapshot = run / "source"
snapshot.mkdir(exist_ok=False)
for path in [*ROOT.glob("*.py"), ROOT / "config.json"]:
    shutil.copy2(path, snapshot / path.name)
start = time.time()
try:
    for stage in ("detect", "track"):
        write_json(run / "status.json", {"status": "running", "stage": stage, "started_at": start})
        subprocess.run([sys.executable, str(ROOT / f"{stage}.py")], check=True, cwd=ROOT)
    write_json(run / "status.json", {"status": "complete", "seconds": time.time() - start})
except Exception as error:
    write_json(run / "status.json", {"status": "failed", "error": str(error), "seconds": time.time() - start})
    raise
