#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${MODELS_DIR:-$HOME/models}"
MODEL_NAME="${MODEL_NAME:-Qwen3-VL-32B-Instruct}"
MAX_LEN="${MAX_LEN:-24576}"
GPU_UTIL="${GPU_UTIL:-0.95}"
START_APP="${START_APP:-1}"

cd "$APP_DIR"
mkdir -p runs

if ! curl -sf http://127.0.0.1:8081/health >/dev/null; then
  VLLM_USE_FLASHINFER_SAMPLER=0 setsid nohup .venv/bin/vllm serve "$MODELS_DIR/$MODEL_NAME" --served-model-name local \
    --host 127.0.0.1 --port 8081 --max-model-len "$MAX_LEN" --gpu-memory-utilization "$GPU_UTIL" \
    --limit-mm-per-prompt '{"image": 32}' --max-logprobs 20 --enable-prefix-caching \
    > runs/vllm.log 2>&1 < /dev/null &
  for _ in $(seq 1 900); do curl -sf http://127.0.0.1:8081/health >/dev/null && break; sleep 2; done
fi
curl -sf http://127.0.0.1:8081/health >/dev/null && echo "vllm ready: $MODEL_NAME"

if [ "$START_APP" = "1" ] && ! curl -sf -H "X-API-Key: ${API_KEY:-dev-key}" http://127.0.0.1:8000/api/v1/health >/dev/null; then
  : "${API_KEY:?set API_KEY}"
  API_KEY="$API_KEY" VLM_CONCURRENCY="${VLM_CONCURRENCY:-8}" MAX_JOBS="${MAX_JOBS:-8}" \
    VLM_PREFILL_BODY='{"continue_final_message": true, "add_generation_prompt": false}' \
    setsid nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > runs/app.log 2>&1 < /dev/null &
  for _ in $(seq 1 30); do curl -sf -H "X-API-Key: ${API_KEY:-dev-key}" http://127.0.0.1:8000/api/v1/health >/dev/null && break; sleep 1; done
  curl -sf -H "X-API-Key: ${API_KEY:-dev-key}" http://127.0.0.1:8000/api/v1/health >/dev/null && echo "app ready on :8000"
fi
