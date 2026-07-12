#!/usr/bin/env bash
# Télécharge le checkpoint Log LLM depuis S3 vers model_prod/ (EC2 app).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/clair-obscur}"
MODEL_DIR="$APP_DIR/src/llm_from_scratch/model_prod"
ENV_FILE="/etc/clair-obscur/app.env"
S3_URI="${LOG_LLM_MODEL_S3_URI:-}"
if [[ -z "$S3_URI" && -f "$ENV_FILE" ]]; then
  S3_URI="$(grep -E '^LOG_LLM_MODEL_S3_URI=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
fi

mkdir -p "$MODEL_DIR"

if [[ -f "$MODEL_DIR/ckpt.pt" ]]; then
  echo "Log LLM: model_prod/ckpt.pt déjà présent ($(du -h "$MODEL_DIR/ckpt.pt" | cut -f1))"
  exit 0
fi

if [[ -z "$S3_URI" ]]; then
  echo "Log LLM: pas de ckpt.pt local et LOG_LLM_MODEL_S3_URI non défini — skip." >&2
  exit 0
fi

echo "Log LLM: téléchargement depuis $S3_URI …"
aws s3 cp "$S3_URI" "$MODEL_DIR/ckpt.pt"
echo "Log LLM: ok ($(du -h "$MODEL_DIR/ckpt.pt" | cut -f1))"
