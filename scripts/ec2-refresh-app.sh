#!/usr/bin/env bash
# Exécuté sur l'EC2 app (SSM ou SSH) après git pull.
set -euo pipefail

APP_DIR="/opt/clair-obscur"
ENV_FILE="/etc/clair-obscur/app.env"

if ! swapon --show | grep -q /swapfile; then
  if [[ ! -f /swapfile ]]; then
    fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile 2>/dev/null || true
fi

PUBLIC_IP="${PUBLIC_IP:-}"
if [[ -z "$PUBLIC_IP" ]]; then
  TOKEN="$(curl -sf -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" || true)"
  if [[ -n "$TOKEN" ]]; then
    PUBLIC_IP="$(curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" \
      http://169.254.169.254/latest/meta-data/public-ipv4 || true)"
  else
    PUBLIC_IP="$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 || true)"
  fi
fi
if [[ -z "$PUBLIC_IP" ]]; then
  echo "public IP introuvable (metadata EC2); export PUBLIC_IP=... avant le script" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  dnf install -y docker-compose-plugin
fi

export NEXT_PUBLIC_API_BASE="http://${PUBLIC_IP}:8020"
if [[ -f "$ENV_FILE" ]]; then
  PK="$(grep -E '^DYNAMODB_PK=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  export NEXT_PUBLIC_DYNAMODB_PK="${PK}"
fi

cd "$APP_DIR"
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
curl -sf "http://127.0.0.1:8020/health" | head -c 400
echo ""
echo "Frontend: http://${PUBLIC_IP}:3000"
echo "API:      http://${PUBLIC_IP}:8020"
