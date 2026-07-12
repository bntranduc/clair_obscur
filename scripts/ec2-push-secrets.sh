#!/usr/bin/env bash
# Écrit /etc/clair-obscur/secrets.env sur l'EC2 app (SSM) puis redémarre le backend.
# Usage (depuis la racine du dépôt) :
#   ./scripts/ec2-push-secrets.sh [fichier_clé_openrouter]
# Défaut : openrout_key.txt à la racine du repo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY_FILE="${1:-$REPO_ROOT/openrout_key.txt}"
REGION="${AWS_REGION:-eu-west-3}"
PROFILE="${AWS_PROFILE:-clair-obscur}"

if [[ ! -f "$KEY_FILE" ]]; then
  echo "Fichier clé introuvable : $KEY_FILE" >&2
  exit 1
fi

KEY="$(tr -d '[:space:]' < "$KEY_FILE")"
if [[ -z "$KEY" ]]; then
  echo "Clé OpenRouter vide dans $KEY_FILE" >&2
  exit 1
fi

INSTANCE_ID="$(terraform -chdir="$REPO_ROOT/src/terraform" output -raw app_instance_id 2>/dev/null || true)"
if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "null" ]]; then
  echo "app_instance_id introuvable (terraform output)" >&2
  exit 1
fi

# Échappe les guillemets simples pour bash distant
ESCAPED_KEY="${KEY//\'/\'\\\'\'}"

CMD_ID="$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters "commands=[\"mkdir -p /etc/clair-obscur && printf '%s\\n' 'OPENROUTER_API_KEY=${ESCAPED_KEY}' 'OPENROUTER_BASE_URL=https://openrouter.ai/api/v1' > /etc/clair-obscur/secrets.env && chmod 600 /etc/clair-obscur/secrets.env && cd /opt/clair-obscur && git fetch origin && git reset --hard origin/main && bash scripts/ec2-refresh-app.sh\"]" \
  --region "$REGION" \
  --profile "$PROFILE" \
  --query Command.CommandId \
  --output text)"

echo "SSM command: $CMD_ID (instance $INSTANCE_ID)"
echo "Attente…"
for _ in $(seq 1 60); do
  STATUS="$(aws ssm get-command-invocation \
    --command-id "$CMD_ID" \
    --instance-id "$INSTANCE_ID" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query Status \
    --output text 2>/dev/null || echo Pending)"
  echo "  status=$STATUS"
  if [[ "$STATUS" == "Success" ]]; then
    echo "Secrets déployés + app redémarrée."
    exit 0
  fi
  if [[ "$STATUS" == "Failed" || "$STATUS" == "Cancelled" || "$STATUS" == "TimedOut" ]]; then
    aws ssm get-command-invocation \
      --command-id "$CMD_ID" \
      --instance-id "$INSTANCE_ID" \
      --region "$REGION" \
      --profile "$PROFILE" \
      --query '{Status:Status,Stderr:StandardErrorContent}' \
      --output json
    exit 1
  fi
  sleep 10
done
echo "Timeout SSM" >&2
exit 1
