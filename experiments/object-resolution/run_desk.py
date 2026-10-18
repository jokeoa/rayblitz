"""Run the table-region comparison only after the baseline has finished."""
import subprocess
import sys
import time

from common import ROOT, read_json, write_json

root = ROOT / "runs"
if read_json(root / "status.json")["status"] != "complete":
    raise ValueError("Finish the baseline before starting desk inference")
if (root / "desk-source").exists():
    raise ValueError("Refusing to overwrite an existing desk experiment")
start = time.time()
try:
    for stage, command in (("detect", ["desk_detect.py"]), ("track", ["track.py", "--desk"])):
        write_json(root / "desk-status.json", {"status": "running", "stage": stage, "started_at": start})
        subprocess.run([sys.executable, *command], check=True, cwd=ROOT)
    write_json(root / "desk-status.json", {"status": "complete", "seconds": time.time()-start})
except Exception as error:
    write_json(root / "desk-status.json", {"status": "failed", "error": str(error)})
    raise
