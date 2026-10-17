#!/usr/bin/env bash
set -euo pipefail

TAG="${LLAMA_TAG:-b9430}"
ARCH="${CUDA_ARCH:-89}"
DEV_IMAGE="${DEV_IMAGE:-nvidia/cuda:12.8.1-devel-ubuntu22.04}"
SRC="$HOME/llama-$TAG"

[ -d "$SRC/.git" ] || git clone --depth 1 --branch "$TAG" https://github.com/ggml-org/llama.cpp "$SRC"

docker run --rm -v "$SRC:/src" -w /src "$DEV_IMAGE" bash -c "
  apt-get update -qq && apt-get install -y -qq cmake build-essential libssl-dev libgomp1 >/dev/null &&
  cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=$ARCH -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release >/dev/null &&
  cmake --build build -j\$(nproc) --target llama-server
"

docker run --rm --gpus all -v "$SRC/build/bin:/app:ro" "$DEV_IMAGE" /app/llama-server --version 2>&1 | tail -2
