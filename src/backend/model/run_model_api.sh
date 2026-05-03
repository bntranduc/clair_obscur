#!/usr/bin/env bash
# Lance l’API minimale ``model_api`` en local (sans Docker). Racine du dépôt = 3 niveaux au-dessus de ce script.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export PYTHONPATH="${ROOT}/src"
exec python3 -m uvicorn backend.model.model_api:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8080}"
