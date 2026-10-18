import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

API_KEY = os.environ.get("API_KEY", "dev-key")
VLM_BASE_URL = os.environ.get("VLM_BASE_URL", "http://127.0.0.1:8081/v1")
VLM_MODEL = os.environ.get("VLM_MODEL", "local")
VLM_CONCURRENCY = int(os.environ.get("VLM_CONCURRENCY", "2"))
VLM_TIMEOUT = float(os.environ.get("VLM_TIMEOUT", "120"))
VLM_EXTRA_BODY = json.loads(os.environ.get("VLM_EXTRA_BODY", "{}"))
VLM_PREFILL_BODY = json.loads(os.environ.get("VLM_PREFILL_BODY", "{}"))

RUNS_DIR = Path(os.environ.get("RUNS_DIR", ROOT / "runs"))
RULES_PATH = Path(os.environ.get("RULES_PATH", ROOT / "rules" / "catalog.json"))
THRESHOLDS_PATH = Path(os.environ.get("THRESHOLDS_PATH", ROOT / "rules" / "thresholds.json"))

PROMPT_FORMAT = os.environ.get("PROMPT_FORMAT", "catalog")
SAMPLE_FPS = float(os.environ.get("SAMPLE_FPS", "2"))
FRAME_WIDTH = int(os.environ.get("FRAME_WIDTH", "336"))
WINDOW_SEC = float(os.environ.get("WINDOW_SEC", "8"))
STRIDE_SEC = float(os.environ.get("STRIDE_SEC", "6"))
MERGE_SEC = float(os.environ.get("MERGE_SEC", "4"))
THRESHOLD = float(os.environ.get("THRESHOLD", "0.5"))
SCORE_NORM = os.environ.get("SCORE_NORM", "window")
CANDIDATE = float(os.environ.get("CANDIDATE", "0.1"))
DETECTOR = os.environ.get("DETECTOR", "on")
COMPOSITE_RULES = [r for r in os.environ.get("COMPOSITE_RULES", "workstation_unlocked,safe_left_open").split(",") if r]
MAX_JOBS = int(os.environ.get("MAX_JOBS", "3"))
DEADLINE_SEC = float(os.environ.get("DEADLINE_SEC", "270"))
JOB_LIMIT_SEC = float(os.environ.get("JOB_LIMIT_SEC", "295"))
CORS_ORIGINS = [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o]
REID_WEIGHTS = Path(os.environ.get("REID_WEIGHTS", ROOT / "models/osnet_x0_25_msmt17.pt"))
