#!/usr/bin/env bash
# Déploie l'infra AWS CLAIR OBSCUR (S3 + DynamoDB) sur le compte du développeur.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/src/terraform"
ENV_FILE="$ROOT/.env"

read_tfvar() {
  local key="$1"
  local default="${2:-}"
  if [[ -f "$TF_DIR/terraform.tfvars" ]]; then
    local value
    value="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$TF_DIR/terraform.tfvars" \
      | head -1 \
      | sed -E 's/^[^=]+=[[:space:]]*"([^"]*)".*/\1/')"
    if [[ -n "$value" ]]; then
      echo "$value"
      return
    fi
  fi
  echo "$default"
}

PROFILE="${AWS_PROFILE:-$(read_tfvar aws_profile clair-obscur)}"
REGION="$(read_tfvar aws_region eu-west-3)"

export AWS_PROFILE="$PROFILE"
export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"

echo "==> Profil AWS : $AWS_PROFILE (région $AWS_REGION)"

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  cat <<EOF
Erreur : credentials AWS introuvables pour le profil « ${AWS_PROFILE} ».

Configure des clés IAM (utilisateur clair-obscur-admin, policy AdministratorAccess) :
  aws configure --profile ${AWS_PROFILE}

Puis vérifie :
  aws sts get-caller-identity --profile ${AWS_PROFILE}

EOF
  exit 1
fi

IDENTITY="$(aws sts get-caller-identity --output json)"
ACCOUNT="$(echo "$IDENTITY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])')"
echo "==> Compte AWS : $ACCOUNT"

if [[ ! -f "$TF_DIR/terraform.tfvars" ]]; then
  cp "$TF_DIR/terraform.tfvars.example" "$TF_DIR/terraform.tfvars"
  echo "==> Créé $TF_DIR/terraform.tfvars (édite aws_profile si besoin)"
fi

cd "$TF_DIR"
terraform init -input=false

APPLY_ARGS=()
if [[ "${1:-}" == "-y" || "${1:-}" == "--auto-approve" ]]; then
  APPLY_ARGS=(-auto-approve)
fi

terraform apply "${APPLY_ARGS[@]}"

SNIPPET="$(terraform output -raw env_snippet)"
echo ""
echo "==> Variables pour .env :"
echo "$SNIPPET"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/.env.example" "$ENV_FILE"
fi

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  key="${line%%=*}"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${line}|" "$ENV_FILE"
  else
    printf '\n%s\n' "$line" >> "$ENV_FILE"
  fi
done <<< "$SNIPPET"

echo ""
echo "==> .env mis à jour ($ENV_FILE)"
echo "    Infra déployée sur le compte $ACCOUNT."

APP_URL="$(terraform output -raw app_api_url 2>/dev/null || true)"
FE_URL="$(terraform output -raw app_frontend_url 2>/dev/null || true)"
if [[ -n "$APP_URL" && "$APP_URL" != "null" ]]; then
  echo ""
  echo "==> App EC2 (prod, sans LOCAL_LOGS_DIR) :"
  echo "    API       $APP_URL"
  echo "    Frontend  $FE_URL"
  echo "    Health    ${APP_URL}/health"
fi
