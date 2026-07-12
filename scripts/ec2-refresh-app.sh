#!/usr/bin/env bash
# Exécuté sur l'EC2 app (SSM ou SSH) après git pull.
set -euo pipefail

APP_DIR="/opt/clair-obscur"
ENV_FILE="/etc/clair-obscur/app.env"
SECRETS_FILE="/etc/clair-obscur/secrets.env"
BACKEND_IMAGE="clair-backend-api:latest"
FRONTEND_IMAGE="clair-frontend:latest"

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

export NEXT_PUBLIC_API_BASE="http://${PUBLIC_IP}:8020"
NEXT_PUBLIC_DYNAMODB_PK=""
if [[ -f "$ENV_FILE" ]]; then
  NEXT_PUBLIC_DYNAMODB_PK="$(grep -E '^DYNAMODB_PK=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
fi

cd "$APP_DIR"

# --- Log LLM local (explain API) ---
LOG_LLM_IMAGE="clair-log-explain:latest"
DOCKER_NET="clair-net"
docker network create "$DOCKER_NET" 2>/dev/null || true

if [[ -f "$APP_DIR/scripts/ec2-sync-log-llm-model.sh" ]]; then
  bash "$APP_DIR/scripts/ec2-sync-log-llm-model.sh" || true
fi

EXPLAIN_ENV_ARGS=()
if [[ -f "$APP_DIR/src/llm_from_scratch/model_prod/ckpt.pt" ]]; then
  docker build -f src/llm_from_scratch/Dockerfile -t "$LOG_LLM_IMAGE" src/llm_from_scratch
  docker stop clair-log-explain 2>/dev/null || true
  docker rm clair-log-explain 2>/dev/null || true
  docker run -d --name clair-log-explain \
    --network "$DOCKER_NET" \
    -p 127.0.0.1:8001:8000 \
    --restart unless-stopped \
    "$LOG_LLM_IMAGE"
  EXPLAIN_ENV_ARGS=(-e "EXPLAIN_LLM_URL=http://clair-log-explain:8000")
  echo "Log LLM: http://127.0.0.1:8001 (docker: clair-log-explain)"
else
  echo "Log LLM: model_prod/ckpt.pt absent — explain API non démarrée." >&2
fi

docker build -f src/api/Dockerfile -t "$BACKEND_IMAGE" .
docker build -f src/frontend/Dockerfile \
  --build-arg "NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}" \
  --build-arg "NEXT_PUBLIC_DYNAMODB_PK=${NEXT_PUBLIC_DYNAMODB_PK}" \
  -t "$FRONTEND_IMAGE" \
  src/frontend

docker stop clair-backend clair-frontend 2>/dev/null || true
docker rm clair-backend clair-frontend 2>/dev/null || true

ENV_ARGS=(--env-file "$ENV_FILE")
if [[ -f "$SECRETS_FILE" ]]; then
  ENV_ARGS+=(--env-file "$SECRETS_FILE")
fi

docker run -d --name clair-backend \
  "${ENV_ARGS[@]}" \
  "${EXPLAIN_ENV_ARGS[@]}" \
  --network "$DOCKER_NET" \
  -p 8020:8020 \
  --restart unless-stopped \
  "$BACKEND_IMAGE"

docker run -d --name clair-frontend \
  -p 3000:3000 \
  --restart unless-stopped \
  "$FRONTEND_IMAGE"

docker ps --filter name=clair-
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf "http://127.0.0.1:8020/health" >/dev/null; then
    break
  fi
  sleep 3
done
curl -sf "http://127.0.0.1:8020/health"
echo ""
if docker ps --format '{{.Names}}' | grep -q '^clair-log-explain$'; then
  curl -sf "http://127.0.0.1:8001/health" && echo ""
fi
curl -sf "http://127.0.0.1:8020/api/v1/agentic/models" | head -c 300
echo ""
curl -sf "http://127.0.0.1:8020/api/v1/alerts" | head -c 200
echo ""
echo "Frontend: http://${PUBLIC_IP}:3000"
echo "API:      http://${PUBLIC_IP}:8020"
