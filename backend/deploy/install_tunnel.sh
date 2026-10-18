#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=/home/ubuntu/cashguard-live
chmod 600 "$ROOT_DIR/secrets/tunnel-token"
sudo tee /etc/systemd/system/cashguard-tunnel.service >/dev/null <<UNIT
[Unit]
Description=CashGuard Cloudflare Tunnel
After=network-online.target cashguard-web.service
Wants=network-online.target
[Service]
User=ubuntu
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run --token-file $ROOT_DIR/secrets/tunnel-token
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now cashguard-tunnel.service
