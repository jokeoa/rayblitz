#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/role-tracking-prototype"
if ! command -v ffmpeg >/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq ffmpeg
fi
"$HOME/.local/bin/uv" venv .venv --python 3.12
"$HOME/.local/bin/uv" pip install --python .venv/bin/python -r requirements.txt
mkdir -p weights runs
.venv/bin/python -c 'import torch,boxmot,transformers; print(torch.__version__, boxmot.__version__, transformers.__version__); print(torch.cuda.get_device_name(0))'
"$HOME/.local/bin/uv" pip freeze --python .venv/bin/python > runs/pip-freeze.txt
