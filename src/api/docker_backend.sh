#!/usr/bin/env bash
# Build / exécution Docker de l’API ``api.main`` (port conteneur 8020).
#
# Usage (depuis n’importe où ; la racine du dépôt est déduite) :
#   bash src/api/docker_backend.sh build
#   bash src/api/docker_backend.sh run              # premier plan, --rm
#   bash src/api/docker_backend.sh run-detached    # arrière-plan, restart unless-stopped
#   bash src/api/docker_backend.sh logs
#   bash src/api/docker_backend.sh stop
#
# Variables optionnelles :
#   BACKEND_IMAGE            défaut clair-backend-api
#   BACKEND_CONTAINER_NAME   défaut clair-backend-api
#   HOST_PORT                port sur la machine hôte (défaut 8020) → mappé sur 8020 dans le conteneur
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${BACKEND_IMAGE:-clair-backend-api}"
NAME="${BACKEND_CONTAINER_NAME:-clair-backend-api}"
HOST_PORT="${HOST_PORT:-8020}"

_env_args() {
  if [[ -f "${ROOT}/.env" ]]; then
    echo --env-file "${ROOT}/.env"
  fi
}

build() {
  docker build -f "${ROOT}/src/api/Dockerfile" -t "$IMAGE" "$ROOT"
}

run() {
  local envf
  envf="$(_env_args || true)"
  # shellcheck disable=SC2086
  docker run --rm -p "${HOST_PORT}:8020" \
    -e AWS_REGION="${AWS_REGION:-eu-west-3}" \
    -e AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-eu-west-3}" \
    $envf \
    "$IMAGE"
}

run_detached() {
  docker rm -f "$NAME" 2>/dev/null || true
  local envf
  envf="$(_env_args || true)"
  # shellcheck disable=SC2086
  docker run -d --name "$NAME" --restart unless-stopped -p "${HOST_PORT}:8020" \
    -e AWS_REGION="${AWS_REGION:-eu-west-3}" \
    -e AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-eu-west-3}" \
    $envf \
    "$IMAGE"
  echo "API → http://0.0.0.0:${HOST_PORT}/ (conteneur ${NAME}, image ${IMAGE})" >&2
}

logs() {
  docker logs -f "$NAME"
}

stop() {
  docker rm -f "$NAME" 2>/dev/null || true
}

case "${1:-}" in
  build) build ;;
  run) run ;;
  run-detached) run_detached ;;
  logs) logs ;;
  stop) stop ;;
  *)
    echo "Usage: $0 build | run | run-detached | logs | stop" >&2
    exit 1
    ;;
esac
