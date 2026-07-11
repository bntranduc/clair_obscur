#!/usr/bin/env bash
# Connecte cette VM à CLAIR OBSCUR : enregistrement → attente approbation → agent actif.
#
# Usage :
#   ./connect.sh --api-url http://15.236.51.2:8020
#   ./connect.sh --api-url http://15.236.51.2:8020 --install   # installe l'agent si absent
#
set -euo pipefail

VM_SETUP_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="/etc/clair-obscur/vm-agent.env"
API_URL=""
DO_INSTALL=0
POLL_INTERVAL="${POLL_INTERVAL:-10}"
MAX_WAIT="${MAX_WAIT:-3600}"

usage() {
  cat <<EOF
Usage: sudo $0 --api-url URL [options]

Options:
  --api-url URL     URL de l'API CLAIR OBSCUR (ex. http://15.236.51.2:8020)
  --install         Lance install.sh (agent + nginx démo) si pas encore installé
  --poll SEC        Intervalle de polling en secondes (défaut: 10)
  --timeout SEC     Timeout attente approbation (défaut: 3600)
  -h, --help        Aide

Étapes :
  1. Enregistre la VM auprès de l'API (statut: pending)
  2. Attend l'approbation admin dans le dashboard (/dashboard/vms)
  3. Configure l'agent pour envoyer les logs via l'API (pas de credentials AWS requis)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url) API_URL="$2"; shift 2 ;;
    --install) DO_INSTALL=1; shift ;;
    --poll) POLL_INTERVAL="$2"; shift 2 ;;
    --timeout) MAX_WAIT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Option inconnue: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Relance avec sudo." >&2
  exit 1
fi

if [[ -z "$API_URL" ]]; then
  echo "Erreur: --api-url requis." >&2
  usage
  exit 1
fi

API_URL="${API_URL%/}"

if [[ "$DO_INSTALL" -eq 1 ]] || [[ ! -f /opt/clair-vm-agent/ship_logs.py ]]; then
  echo "==> Installation de l'agent VM…"
  bash "$VM_SETUP_DIR/install.sh" --profile demo
fi

mkdir -p /etc/clair-obscur

HOSTNAME="$(hostname)"
FINGERPRINT="$( (cat /etc/machine-id 2>/dev/null || cat /var/lib/dbus/machine-id 2>/dev/null || echo "") | tr -d '\n')"

# Charger token existant si déjà enregistré
EXISTING_TOKEN=""
if [[ -f "$ENV_FILE" ]]; then
  EXISTING_TOKEN="$(grep -E '^VM_API_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
fi

register_vm() {
  export HOSTNAME FINGERPRINT
  local payload
  payload=$(python3 - <<PY
import json, os
print(json.dumps({
    "hostname": os.environ["HOSTNAME"],
    "fingerprint": os.environ.get("FINGERPRINT", ""),
    "metadata": {"os": "$(uname -s)", "connect_script": "vm_setup/connect.sh"},
}))
PY
)
  curl -sf -X POST "${API_URL}/api/v1/vms/register" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

if [[ -z "$EXISTING_TOKEN" ]]; then
  echo "==> Enregistrement de la VM ($HOSTNAME)…"
  RESP="$(register_vm)"
  VM_ID="$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['vm_id'])")"
  EXISTING_TOKEN="$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['api_token'])")"
  echo "    VM ID : $VM_ID"
  echo "    Statut: en attente d'approbation admin"
  echo "    → Dashboard : http://$(echo "$API_URL" | sed -E 's/:8020.*//'):3000/dashboard/vms"
else
  echo "==> Token existant trouvé, reprise de la connexion…"
fi

# Mettre à jour la config agent
touch "$ENV_FILE"
grep -v -E '^(API_BASE|VM_API_TOKEN|SHIP_MODE|VM_ID)=' "$ENV_FILE" > "${ENV_FILE}.tmp" || true
mv "${ENV_FILE}.tmp" "$ENV_FILE"
cat >> "$ENV_FILE" <<EOF
API_BASE=${API_URL}
VM_API_TOKEN=${EXISTING_TOKEN}
SHIP_MODE=api
VM_ID=${HOSTNAME}
EOF
chmod 600 "$ENV_FILE"

poll_status() {
  curl -sf "${API_URL}/api/v1/vms/me" \
    -H "Authorization: Bearer ${EXISTING_TOKEN}"
}

echo "==> Attente de l'approbation admin (max ${MAX_WAIT}s)…"
START=$(date +%s)
while true; do
  NOW=$(date +%s)
  ELAPSED=$((NOW - START))
  if [[ "$ELAPSED" -ge "$MAX_WAIT" ]]; then
    echo "Timeout: l'admin n'a pas approuvé dans le délai imparti." >&2
    echo "Relance ce script plus tard — le token est sauvegardé dans $ENV_FILE" >&2
    exit 2
  fi

  STATUS_RESP="$(poll_status)" || { echo "Erreur API, nouvel essai…"; sleep "$POLL_INTERVAL"; continue; }
  STATUS="$(echo "$STATUS_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))")"
  echo "    statut=$STATUS (${ELAPSED}s)"

  case "$STATUS" in
    approved)
      S3_PREFIX="$(echo "$STATUS_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('s3_prefix',''))")"
      echo ""
      echo "✓ VM approuvée ! Préfixe S3 : $S3_PREFIX"
      systemctl daemon-reload 2>/dev/null || true
      systemctl restart clair-vm-agent 2>/dev/null || true
      echo "  Agent redémarré. Logs : journalctl -u clair-vm-agent -f"
      exit 0
      ;;
    rejected|revoked)
      echo "✗ Connexion refusée ou révoquée (statut: $STATUS)." >&2
      exit 1
      ;;
    pending)
      sleep "$POLL_INTERVAL"
      ;;
    *)
      sleep "$POLL_INTERVAL"
      ;;
  esac
done
