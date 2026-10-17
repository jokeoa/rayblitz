#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${MODELS_DIR:-$HOME/models}"
MODEL_REPO="${MODEL_REPO:-Qwen/Qwen3-VL-32B-Instruct}"

SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "== system packages"
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq ffmpeg curl python3-venv python3-pip >/dev/null
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

echo "== python env"
cd "$APP_DIR"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q vllm "huggingface_hub[cli]" fastapi "uvicorn[standard]" python-multipart httpx pillow openpyxl numpy scikit-learn
.venv/bin/python -c "import vllm, app.main; print('vllm', vllm.__version__, 'app ok')"

echo "== model $MODEL_REPO"
mkdir -p "$MODELS_DIR"
.venv/bin/hf download "$MODEL_REPO" --local-dir "$MODELS_DIR/$(basename "$MODEL_REPO")" >/dev/null
du -sh "$MODELS_DIR/$(basename "$MODEL_REPO")"
df -h "$MODELS_DIR" | tail -1

echo "== done"
