#!/usr/bin/env bash
# Environnement Python local pour le backend.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -r src/api/requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Créé .env depuis .env.example (LOCAL_LOGS_DIR=data/sample_logs)"
fi

echo ""
echo "Setup terminé. Lancer l’API :"
echo "  source .venv/bin/activate && ./src/api/run.sh"
