#!/usr/bin/env bash
# Lance l’API dashboard (logs S3). Depuis la racine du dépôt :
#   ./src/api/run.sh
# Prérequis : pip install -r src/api/requirements.txt ; AWS credentials pour S3.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONPATH="$ROOT/src"
exec uvicorn api.main:app --host "${HOST:-0.0.0.0}" --port "${API_PORT:-8020}"
