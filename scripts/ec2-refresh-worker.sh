#!/usr/bin/env bash
# Exécuté sur l'EC2 worker (SSM ou SSH) après git pull.
set -euo pipefail

APP_DIR="/opt/clair-obscur"
ENV_FILE="/etc/clair-obscur/worker.env"
IMAGE="clair-predict-worker:latest"

if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
fi

cd "$APP_DIR"
docker build -f src/backend/worker/Dockerfile -t "$IMAGE" .

cat > /etc/systemd/system/clair-predict-worker.service <<'UNITEOF'
[Unit]
Description=Clair Obscur SQS predict worker (Docker)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=simple
Restart=always
RestartSec=15
ExecStartPre=-/usr/bin/docker stop clair-predict-worker
ExecStartPre=-/usr/bin/docker rm clair-predict-worker
ExecStart=/usr/bin/docker run --name clair-predict-worker --env-file /etc/clair-obscur/worker.env clair-predict-worker:latest
ExecStop=/usr/bin/docker stop clair-predict-worker

[Install]
WantedBy=multi-user.target
UNITEOF

systemctl daemon-reload
systemctl restart clair-predict-worker
systemctl is-active --quiet clair-predict-worker
echo "clair-predict-worker is active"
