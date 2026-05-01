#!/usr/bin/env bash
# Lance l’API dashboard FastAPI (logs S3 + alertes) sur le port attendu par le frontend (8010).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src"
export AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-west-3}}"
# 0.0.0.0 : joignable depuis l’extérieur (EC2, proxy Amplify). 127.0.0.1 = connection refused pour les clients distants.
UVICORN_HOST="${UVICORN_HOST:-0.0.0.0}"
exec python3 -m uvicorn backend.dashboard.main:app --host "$UVICORN_HOST" --port 8010 --reload
