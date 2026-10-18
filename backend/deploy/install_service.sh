#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SLOTS="${SLOTS:-4}"
: "${API_KEY:?set API_KEY}"

umask 077
printf 'API_KEY=%s\n' "$API_KEY" > "$APP_DIR/.env"

sudo tee /etc/systemd/system/cashguard.service >/dev/null <<EOF
[Unit]
Description=CashGuard API
After=network-online.target docker.service
Wants=network-online.target

[Service]
User=$(id -un)
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment=VLM_CONCURRENCY=$SLOTS MAX_JOBS=$((SLOTS + 2)) HF_HUB_OFFLINE=1
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now cashguard
for _ in $(seq 1 60); do curl -sf -H "X-API-Key: ${API_KEY:-dev-key}" http://127.0.0.1:8000/api/v1/health >/dev/null && break; sleep 1; done
curl -sf -H "X-API-Key: ${API_KEY:-dev-key}" http://127.0.0.1:8000/api/v1/health && echo " cashguard.service ready on :8000"
