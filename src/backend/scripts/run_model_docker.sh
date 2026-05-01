#!/usr/bin/env bash
set -euo pipefail
# Lance l’API modèle ; ajoute ``--profile sqs`` pour le worker SQS.
# Les options globales ``docker compose`` (ex. ``--profile sqs``) doivent précéder ``up``.
#
# Exemples :
#   ./src/backend/scripts/run_model_docker.sh
#   ./src/backend/scripts/run_model_docker.sh --profile sqs
#   ./src/backend/scripts/run_model_docker.sh --profile sqs -d

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
COMPOSE_FILE=docker-compose.model.yml

PROFILES=()
UP_TAIL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      [[ -n "${2:-}" ]] || { echo "missing value for --profile" >&2; exit 1; }
      PROFILES+=(--profile "$2")
      shift 2
      ;;
    *)
      UP_TAIL+=("$1")
      shift
      ;;
  esac
done

_run() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "${PROFILES[@]}" -f "$COMPOSE_FILE" up --build "${UP_TAIL[@]}"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "${PROFILES[@]}" -f "$COMPOSE_FILE" up --build "${UP_TAIL[@]}"
  else
    echo "Docker Compose introuvable." >&2
    exit 1
  fi
}

_run
