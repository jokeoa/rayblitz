#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="/home/ubuntu/cashguard-live"
PYTHON_ENV="/home/ubuntu/role-tracking-prototype/.venv"
mkdir -p "$ROOT_DIR/runs" "$ROOT_DIR/secrets"
chmod 700 "$ROOT_DIR/secrets"
if [ ! -f "$ROOT_DIR/secrets/service.env" ]; then
  "$PYTHON_ENV/bin/python" - <<'PY'
from pathlib import Path
import secrets
p=Path('/home/ubuntu/cashguard-live/secrets/service.env')
p.write_text('API_KEY='+secrets.token_urlsafe(32)+'\nVLM_CONCURRENCY=2\nMAX_JOBS=1\nHF_HUB_OFFLINE=1\nRUNS_DIR=/home/ubuntu/cashguard-live/runs\nREID_WEIGHTS=/home/ubuntu/role-tracking-prototype/weights/osnet_x0_25_msmt17.pt\n')
p.chmod(0o600)
PY
fi
sudo tee /etc/systemd/system/cashguard-api.service >/dev/null <<UNIT
[Unit]
Description=CashGuard production analysis API
After=network-online.target docker.service
[Service]
User=ubuntu
WorkingDirectory=$ROOT_DIR/backend
EnvironmentFile=$ROOT_DIR/secrets/service.env
ExecStart=$PYTHON_ENV/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
TimeoutStopSec=30
[Install]
WantedBy=multi-user.target
UNIT
sudo tee /etc/systemd/system/cashguard-web.service >/dev/null <<UNIT
[Unit]
Description=CashGuard review frontend
After=network-online.target cashguard-api.service
[Service]
User=ubuntu
WorkingDirectory=$ROOT_DIR/app
Environment=NODE_ENV=production
Environment=PATH=$ROOT_DIR/runtime/node/bin:/usr/local/bin:/usr/bin:/bin
Environment=ANALYSIS_API_URL=http://127.0.0.1:8000/api/v1
Environment=SESSION_DB=$ROOT_DIR/secrets/sessions.sqlite
ExecStart=$ROOT_DIR/runtime/node/bin/node node_modules/srvx/bin/srvx.mjs serve --prod --host 127.0.0.1 --port 3000 --static ../client --entry dist/server/server.js
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable cashguard-api.service cashguard-web.service
sudo systemctl restart cashguard-api.service cashguard-web.service
