#!/usr/bin/env bash
# Upload du checkpoint prod vers S3 (une fois, depuis la machine de dev).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CKPT="$ROOT/src/llm_from_scratch/model_prod/ckpt.pt"
BUCKET="${LOG_LLM_MODEL_BUCKET:-clair-obscur-904233105374-predictions}"
KEY="${LOG_LLM_MODEL_S3_KEY:-artifacts/log-llm/ckpt.pt}"
PROFILE="${AWS_PROFILE:-clair-obscur}"
REGION="${AWS_REGION:-eu-west-3}"

if [[ ! -f "$CKPT" ]]; then
  echo "Checkpoint introuvable: $CKPT" >&2
  exit 1
fi

DEST="s3://${BUCKET}/${KEY}"
echo "Upload $CKPT → $DEST"
aws s3 cp "$CKPT" "$DEST" --region "$REGION" --profile "$PROFILE"
echo "Définir sur l'EC2 app: LOG_LLM_MODEL_S3_URI=$DEST"
