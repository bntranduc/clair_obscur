#!/usr/bin/env bash
set -euo pipefail
# Lance l’API HTTP logs S3 (port 8020 par défaut).
# Prérequis : pip install -r src/api/requirements.txt
#             aws sso login + export AWS_PROFILE=… (optionnel si rôle IAM / env vars)

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/src"
export AWS_REGION="${AWS_REGION:-eu-west-3}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"
PORT="${API_PORT:-8020}"

exec python3 -m uvicorn api.main:app --host "${API_HOST:-0.0.0.0}" --port "$PORT"
