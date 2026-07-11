#!/usr/bin/env bash
# Lance l’API dashboard en local. Depuis la racine du dépôt :
#   ./src/api/run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export PYTHONPATH="$ROOT/src"
PORT="${API_PORT:-8020}"
HOST="${HOST:-127.0.0.1}"

if command -v ss >/dev/null 2>&1; then
  if ss -tln | grep -q ":${PORT} "; then
    echo "Erreur : le port ${PORT} est déjà utilisé."
    echo "  → Arrêter Docker : docker compose down"
    echo "  → Ou changer le port : API_PORT=8021 ./src/api/run.sh"
    exit 1
  fi
fi

echo "CLAIR OBSCUR API — http://${HOST}:${PORT}"
echo "  LOCAL_LOGS_DIR=${LOCAL_LOGS_DIR:-<non défini>}"
echo "  alerts → database/alerts.json"
echo ""

if [[ "${RELOAD:-1}" == "1" ]]; then
  exec python3 -m uvicorn api.main:app --host "$HOST" --port "$PORT" --reload
else
  exec python3 -m uvicorn api.main:app --host "$HOST" --port "$PORT"
fi
