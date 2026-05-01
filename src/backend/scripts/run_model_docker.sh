#!/usr/bin/env bash
set -euo pipefail
# Lance l’API modèle (service ``model``). Ajoute le worker SQS avec le profil Compose ``sqs``.
#
# Exemples :
#   ./src/backend/scripts/run_model_docker.sh
#   ./src/backend/scripts/run_model_docker.sh --profile sqs
#   ./src/backend/scripts/run_model_docker.sh --profile sqs -d
#
# Prérequis AWS : aws sso login + export AWS_PROFILE=… ; SQS_QUEUE_URL dans .env pour le worker.

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
COMPOSE_FILE=docker-compose.model.yml

if docker compose version >/dev/null 2>&1; then
  exec docker compose -f "$COMPOSE_FILE" up --build "$@"
elif command -v docker-compose >/dev/null 2>&1; then
  exec docker-compose -f "$COMPOSE_FILE" up --build "$@"
fi

echo "Docker Compose introuvable." >&2
exit 1
