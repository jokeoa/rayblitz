#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${MODELS_DIR:-$HOME/models}"
LLAMA_DIR="${LLAMA_DIR:-$HOME/llama.cpp}"
LLAMA_IMAGE="${LLAMA_IMAGE:-ghcr.io/ggml-org/llama.cpp:server-cuda}"
BUILT_SRC="${BUILT_SRC:-$HOME/llama-${LLAMA_TAG:-b9430}}"
DEV_IMAGE="${DEV_IMAGE:-nvidia/cuda:12.8.1-devel-ubuntu22.04}"
SLOTS="${SLOTS:-4}"
START_APP="${START_APP:-1}"

cd "$APP_DIR"
mkdir -p runs

NATIVE=0
[ -x "$LLAMA_DIR/build/bin/llama-server" ] && NATIVE=1
M=/models
[ "$NATIVE" = "1" ] && M="$MODELS_DIR"
ARGS=(-m "$M/${MODEL_FILE:-Qwen3.5-9B-Q4_K_M.gguf}" --mmproj "$M/${MMPROJ_FILE:-mmproj-Qwen3.5-9B-BF16.gguf}"
      --port 8081 -c $((16384 * SLOTS)) -np "$SLOTS" -ngl 99
      --image-max-tokens "${IMAGE_TOKENS:-256}" --reasoning off --cache-ram "${CACHE_RAM:-1024}")

if ! curl -sf http://127.0.0.1:8081/health >/dev/null; then
  if [ "$NATIVE" = "1" ]; then
    nohup "$LLAMA_DIR/build/bin/llama-server" "${ARGS[@]}" --host 127.0.0.1 > runs/llama.log 2>&1 &
  else
    docker rm -f llama >/dev/null 2>&1 || true
    if [ -x "$BUILT_SRC/build/bin/llama-server" ]; then
      docker run -d --name llama --gpus all --restart unless-stopped \
        -p 127.0.0.1:8081:8081 -v "$MODELS_DIR:/models:ro" -v "$BUILT_SRC:/src:ro" \
        "$DEV_IMAGE" /src/build/bin/llama-server "${ARGS[@]}" --host 0.0.0.0 >/dev/null
    else
      docker run -d --name llama --gpus all --restart unless-stopped \
        -p 127.0.0.1:8081:8081 -v "$MODELS_DIR:/models:ro" \
        "$LLAMA_IMAGE" "${ARGS[@]}" --checkpoint-min-step 256 --host 0.0.0.0 >/dev/null
    fi
  fi
  for _ in $(seq 1 240); do curl -sf http://127.0.0.1:8081/health >/dev/null && break; sleep 1; done
fi
curl -sf http://127.0.0.1:8081/health && echo " llama-server ready"

if [ "$START_APP" = "1" ] && ! curl -sf -H "X-API-Key: ${API_KEY:-dev-key}" http://127.0.0.1:8000/api/v1/health >/dev/null; then
  : "${API_KEY:?set API_KEY}"
  API_KEY="$API_KEY" VLM_CONCURRENCY="$SLOTS" MAX_JOBS=$((SLOTS + 2)) HF_HUB_OFFLINE=1 \
    nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > runs/app.log 2>&1 &
  for _ in $(seq 1 30); do curl -sf -H "X-API-Key: ${API_KEY:-dev-key}" http://127.0.0.1:8000/api/v1/health >/dev/null && break; sleep 1; done
  curl -sf -H "X-API-Key: ${API_KEY:-dev-key}" http://127.0.0.1:8000/api/v1/health && echo " app ready on :8000"
fi
