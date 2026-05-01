#!/usr/bin/env bash
# Lance l’API dashboard FastAPI (logs S3 + alertes) sur le port attendu par le frontend (8010).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src"
export AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-west-3}}"
exec python3 -m uvicorn backend.dashboard.main:app --host 127.0.0.1 --port 8010 --reload
