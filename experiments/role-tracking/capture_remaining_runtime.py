"""Capture only reproducibility metadata; never export environment credentials."""
import importlib.metadata
import platform
import subprocess
from pathlib import Path

from common import ROOT, sha256, write_json

OUT = ROOT / 'runs/remaining-videos'
models = Path('/home/ubuntu/models')
backend = Path('/home/ubuntu/cashguard')
metadata = {
    'python': platform.python_version(),
    'packages': {p: importlib.metadata.version(p) for p in ('torch', 'transformers', 'boxmot', 'numpy', 'pillow', 'httpx', 'scipy')},
    'gpu': subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'], text=True).strip(),
    'llama_image': subprocess.check_output(['docker', 'inspect', 'cashguard-remaining-llama', '--format', '{{.Image}}'], text=True).strip(),
    'models': {p.name: sha256(p) for p in models.glob('*.gguf')},
    'backend_code': {str(p.relative_to(backend)): sha256(p) for p in (backend / 'app').rglob('*.py')},
    'runner': sha256(backend / 'eval/run_reference_batch.py'),
    'experiment_code': {p: sha256(ROOT / p) for p in ('detect.py', 'reference_track.py', 'reference_policy.py', 'remaining_report.py', 'validate_remaining.py')},
    'sampling': {'tracking_fps': 10, 'action_fps': 2, 'action_frame_width': 336},
    'role_ground_truth_on_targets': False,
}
write_json(OUT / 'runtime.json', metadata)
print('Runtime metadata saved without credentials')
