#!/usr/bin/env bash
set -euo pipefail
# Usage (depuis n'importe quel répertoire) :
#   ./src/backend/scripts/run_model_serve.sh
# PYTHONPATH doit pointer vers le répertoire qui contient le package ``backend`` (…/clair_obscur/src).

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export PYTHONPATH="$ROOT/src"
exec uvicorn api.model_app:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8080}"
