#!/usr/bin/env bash
set -euo pipefail
# Lance l’API modèle via Docker (racine du dépôt).
# Avant : aws sso login --profile … puis export AWS_PROFILE=… (sauf rôle IAM seul sur EC2).
#
# Usage :
#   ./src/backend/scripts/run_model_docker.sh       # premier plan
#   ./src/backend/scripts/run_model_docker.sh -d    # détaché

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
COMPOSE_FILE=docker-compose.model.yml

DETACH=()
[[ "${1:-}" == "-d" ]] && DETACH=(-d)

_run() {
  if docker compose version >/dev/null 2>&1; then
    docker compose -f "$COMPOSE_FILE" up --build "${DETACH[@]}"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose -f "$COMPOSE_FILE" up --build "${DETACH[@]}"
  else
    echo "Docker Compose introuvable. Installe le plugin ou docker-compose." >&2
    echo "Alternative :" >&2
    echo "  docker build -f src/backend/model/Dockerfile -t clair-model ." >&2
    echo "  docker run --rm -p 8080:8080 -e AWS_REGION=eu-west-3 -e AWS_PROFILE=\${AWS_PROFILE:-} \\" >&2
    echo "    -v \"\$HOME/.aws:/root/.aws:ro\" clair-model" >&2
    exit 1
  fi
}

_run
