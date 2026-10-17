#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${MODELS_DIR:-$HOME/models}"
LLAMA_DIR="${LLAMA_DIR:-$HOME/llama.cpp}"
LLAMA_TAG="${LLAMA_TAG:-b9430}"
LLAMA_IMAGE="${LLAMA_IMAGE:-ghcr.io/ggml-org/llama.cpp:server-cuda}"
HF_REPO="https://huggingface.co/lmstudio-community/Qwen3.5-9B-GGUF/resolve/main"

SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "== system packages"
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq ffmpeg curl python3-venv python3-pip >/dev/null

echo "== GPU"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

echo "== llama.cpp"
if docker run --rm --gpus all "$LLAMA_IMAGE" --version >/dev/null 2>&1 || { docker pull -q "$LLAMA_IMAGE" >/dev/null && docker run --rm --gpus all "$LLAMA_IMAGE" --version >/dev/null 2>&1; }; then
  echo "docker image $LLAMA_IMAGE"
  docker run --rm --gpus all "$LLAMA_IMAGE" --version 2>&1 | head -1
elif command -v nvcc >/dev/null; then
  $SUDO apt-get install -y -qq git cmake build-essential >/dev/null
  if [ ! -x "$LLAMA_DIR/build/bin/llama-server" ]; then
    rm -rf "$LLAMA_DIR"
    git clone --depth 1 --branch "$LLAMA_TAG" https://github.com/ggml-org/llama.cpp "$LLAMA_DIR"
    cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=native -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release >/dev/null
    cmake --build "$LLAMA_DIR/build" --config Release -j "$(nproc)" --target llama-server
  fi
  "$LLAMA_DIR/build/bin/llama-server" --version 2>&1 | head -1
else
  echo "neither docker with GPU nor nvcc is available"
  exit 1
fi

echo "== model weights"
mkdir -p "$MODELS_DIR"
for f in Qwen3.5-9B-Q4_K_M.gguf mmproj-Qwen3.5-9B-BF16.gguf; do
  [ -s "$MODELS_DIR/$f" ] || curl -fL --retry 3 -s -o "$MODELS_DIR/$f" "$HF_REPO/$f"
done
ls -l "$MODELS_DIR"

echo "== python env"
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q fastapi "uvicorn[standard]" python-multipart httpx pillow openpyxl
.venv/bin/pip install -q torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.venv/bin/pip install -q transformers==5.20.1 scipy==1.15.3
.venv/bin/python -c "from transformers import AutoImageProcessor, AutoModelForObjectDetection as M; AutoImageProcessor.from_pretrained('PekingU/rtdetr_v2_r50vd'); M.from_pretrained('PekingU/rtdetr_v2_r50vd'); from transformers import Owlv2Processor, Owlv2ForObjectDetection; Owlv2Processor.from_pretrained('google/owlv2-base-patch16-ensemble'); Owlv2ForObjectDetection.from_pretrained('google/owlv2-base-patch16-ensemble')"
.venv/bin/python -c "import app.main; print('app imports ok')"

echo "== done"
