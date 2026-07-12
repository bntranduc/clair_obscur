#!/usr/bin/env bash
# Upload du checkpoint prod vers S3 (depuis la machine de dev).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CKPT="$ROOT/src/llm_from_scratch/model_prod/ckpt.pt"
KEY="${LOG_LLM_MODEL_S3_KEY:-artifacts/log-llm/ckpt.pt}"
REGION="${AWS_REGION:-eu-west-3}"
PROFILE="${AWS_PROFILE:-}"

if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1090
  source "$ROOT/.env" 2>/dev/null || true
fi

BUCKET="${LOG_LLM_MODEL_BUCKET:-${PREDICTIONS_BUCKET:-}}"
if [[ -z "$BUCKET" ]]; then
  BUCKET="$(terraform -chdir="$ROOT/src/terraform" output -raw predictions_bucket_name 2>/dev/null || true)"
fi
if [[ -z "$BUCKET" || "$BUCKET" == "null" ]]; then
  echo "Bucket introuvable — lance d'abord ./deploy-all.sh ou définis PREDICTIONS_BUCKET." >&2
  exit 1
fi

if [[ ! -f "$CKPT" ]]; then
  echo "Checkpoint introuvable: $CKPT" >&2
  exit 1
fi

DEST="s3://${BUCKET}/${KEY}"
AWS_ARGS=(--region "$REGION")
[[ -n "${PROFILE:-}" ]] && AWS_ARGS+=(--profile "$PROFILE")

echo "Upload $CKPT → $DEST"
aws s3 cp "$CKPT" "$DEST" "${AWS_ARGS[@]}"
echo "LOG_LLM_MODEL_S3_URI=$DEST"
