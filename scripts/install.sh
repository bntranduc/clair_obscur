#!/usr/bin/env bash
# Installation complète CLAIR OBSCUR sur une machine fraîche :
#   1. Copier .env.example → .env et renseigner credentials + GIT_REPO_URL
#   2. Activer Bedrock Sonnet dans la console AWS (eu-west-3)
#   3. ./scripts/install.sh
#
# Déploie : S3, DynamoDB, SQS, EC2 worker, EC2 app (API + frontend).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/src/terraform"
ENV_FILE="$ROOT/.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}==>${NC} $*"; }
fail()  { echo -e "${RED}Erreur:${NC} $*" >&2; exit 1; }

# --- Chargement .env ---
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/.env.example" "$ENV_FILE"
  fail "Créé $ENV_FILE — renseigne tes credentials AWS puis relance ./scripts/install.sh"
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-west-3}}"
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"

if [[ -n "${AWS_PROFILE:-}" ]]; then
  export AWS_PROFILE
fi

GIT_REPO_URL="${GIT_REPO_URL:-${WORKER_GIT_REPO_URL:-https://github.com/bntranduc/clair_obscur.git}}"
GIT_REF="${GIT_REF:-${WORKER_GIT_REF:-main}}"
BEDROCK_MODEL_ID="${BEDROCK_MODEL_ID:-eu.anthropic.claude-sonnet-4-6}"
WORKER_INSTANCE_TYPE="${WORKER_INSTANCE_TYPE:-t3.small}"
APP_INSTANCE_TYPE="${APP_INSTANCE_TYPE:-t2.medium}"
INSTALL_UPLOAD_DEMO="${INSTALL_UPLOAD_DEMO:-1}"
INSTALL_WAIT_TIMEOUT="${INSTALL_WAIT_TIMEOUT:-1800}"

# --- Prérequis binaires ---
need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Commande « $1 » introuvable. Installe-la puis relance."
}

info "Vérification des prérequis…"
need_cmd aws
need_cmd terraform
need_cmd git
need_cmd python3
need_cmd curl

# --- Credentials AWS ---
info "Vérification credentials AWS (région $AWS_REGION)…"
if ! IDENTITY="$(aws sts get-caller-identity --output json 2>/dev/null)"; then
  cat >&2 <<EOF
${RED}Credentials AWS invalides.${NC}

Option A — profil CLI :
  aws configure --profile clair-obscur
  # puis dans .env : AWS_PROFILE=clair-obscur

Option B — clés dans .env :
  AWS_ACCESS_KEY_ID=...
  AWS_SECRET_ACCESS_KEY=...
  AWS_REGION=eu-west-3
  # laisser AWS_PROFILE vide

EOF
  exit 1
fi

ACCOUNT="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])' <<< "$IDENTITY")"
info "Compte AWS : $ACCOUNT"

# --- Bedrock (accès modèle) ---
check_bedrock() {
  info "Vérification accès Bedrock ($BEDROCK_MODEL_ID)…"
  if aws bedrock get-foundation-model \
    --model-identifier "$BEDROCK_MODEL_ID" \
    --region "$AWS_REGION" >/dev/null 2>&1; then
    info "Modèle Bedrock accessible."
    return 0
  fi
  warn "Modèle Bedrock non accessible ou non activé."
  cat <<EOF

Active le modèle dans la console AWS :
  Bedrock → Model access → ${BEDROCK_MODEL_ID}
  Région : ${AWS_REGION}

Puis relance : ./scripts/install.sh

EOF
  exit 1
}
check_bedrock

# --- Code sur GitHub (EC2 clone ce dépôt) ---
info "Dépôt EC2 : $GIT_REPO_URL (ref: $GIT_REF)"
if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  REMOTE="$(git -C "$ROOT" remote get-url origin 2>/dev/null || true)"
  AHEAD="$(git -C "$ROOT" rev-list --count "@{u}..HEAD" 2>/dev/null || echo 0)"
  if [[ "$AHEAD" -gt 0 ]]; then
    warn "$AHEAD commit(s) local(aux) non poussé(s) sur origin."
    if [[ "${INSTALL_GIT_PUSH:-0}" == "1" ]]; then
      info "Push vers origin ($GIT_REF)…"
      git -C "$ROOT" push origin "HEAD:${GIT_REF}"
    else
      warn "Les EC2 cloneront le code distant, pas tes commits locaux."
      warn "Pousse avec : git push origin ${GIT_REF}   ou   INSTALL_GIT_PUSH=1 ./scripts/install.sh"
    fi
  fi
  if [[ -n "$REMOTE" && "$REMOTE" != "$GIT_REPO_URL" ]]; then
    warn "GIT_REPO_URL=$GIT_REPO_URL ≠ origin=$REMOTE — vérifie .env"
  fi
fi

# --- terraform.tfvars depuis .env ---
TF_PROFILE="${AWS_PROFILE:-clair-obscur}"
if [[ -n "${AWS_ACCESS_KEY_ID:-}" && -z "${AWS_PROFILE:-}" ]]; then
  TF_PROFILE=""
fi

info "Génération $TF_DIR/terraform.tfvars"
cat > "$TF_DIR/terraform.tfvars" <<EOF
aws_region   = "${AWS_REGION}"
aws_profile  = "${TF_PROFILE}"
project_name = "clair-obscur"
environment  = "dev"

force_destroy = true

raw_logs_prefix    = "raw/opensearch/logs-raw"
predictions_prefix = "predictions"
enable_versioning  = true

dynamodb_demo_day = "2026-01-12"

worker_instance_type    = "${WORKER_INSTANCE_TYPE}"
worker_git_repo_url     = "${GIT_REPO_URL}"
worker_git_ref          = "${GIT_REF}"
worker_bedrock_model_id = "${BEDROCK_MODEL_ID}"

enable_ec2_app     = true
app_instance_type  = "${APP_INSTANCE_TYPE}"

enable_ec2_demo_vm      = true
demo_vm_instance_type   = "${DEMO_VM_INSTANCE_TYPE:-t3.micro}"
EOF

# --- Terraform ---
info "Terraform init + apply (≈ 3–5 min)…"
cd "$TF_DIR"
terraform init -input=false
terraform apply -auto-approve

SNIPPET="$(terraform output -raw env_snippet)"
APP_ID="$(terraform output -raw app_instance_id 2>/dev/null || true)"
WORKER_ID="$(terraform output -raw predict_worker_instance_id 2>/dev/null || true)"
APP_IP="$(terraform output -raw app_public_ip 2>/dev/null || true)"
API_URL="$(terraform output -raw app_api_url 2>/dev/null || true)"
FE_URL="$(terraform output -raw app_frontend_url 2>/dev/null || true)"

# --- Sync .env ---
info "Mise à jour $ENV_FILE"
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  key="${line%%=*}"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${line}|" "$ENV_FILE"
  else
    printf '\n%s\n' "$line" >> "$ENV_FILE"
  fi
done <<< "$SNIPPET"

# Conserver GIT_REPO_URL / GIT_REF dans .env
for kv in "GIT_REPO_URL=${GIT_REPO_URL}" "GIT_REF=${GIT_REF}"; do
  key="${kv%%=*}"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${kv}|" "$ENV_FILE"
  else
    echo "$kv" >> "$ENV_FILE"
  fi
done

# --- Attente EC2 + SSM ---
wait_ssm_online() {
  local id="$1" label="$2"
  local elapsed=0
  info "Attente SSM ($label: $id)…"
  while [[ "$elapsed" -lt "$INSTALL_WAIT_TIMEOUT" ]]; do
    status="$(aws ssm describe-instance-information \
      --filters "Key=InstanceIds,Values=${id}" \
      --region "$AWS_REGION" \
      --query 'InstanceInformationList[0].PingStatus' \
      --output text 2>/dev/null || echo "None")"
    if [[ "$status" == "Online" ]]; then
      info "$label SSM en ligne."
      return 0
    fi
    sleep 15
    elapsed=$((elapsed + 15))
  done
  fail "Timeout SSM pour $label ($id)"
}

run_ssm() {
  local id="$1"
  shift
  local json='['
  local first=1
  for c in "$@"; do
    [[ $first -eq 1 ]] || json+=','
    first=0
    local esc
    esc="$(printf '%s' "$c" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    json+="\"${esc}\""
  done
  json+=']'
  aws ssm send-command \
    --instance-ids "$id" \
    --document-name AWS-RunShellScript \
    --parameters "commands=${json}" \
    --region "$AWS_REGION" \
    --query Command.CommandId \
    --output text
}

wait_ssm_command() {
  local cmd_id="$1" instance_id="$2" label="$3"
  local elapsed=0
  while [[ "$elapsed" -lt "$INSTALL_WAIT_TIMEOUT" ]]; do
    read -r status code <<< "$(aws ssm get-command-invocation \
      --command-id "$cmd_id" \
      --instance-id "$instance_id" \
      --region "$AWS_REGION" \
      --query '[Status,ResponseCode]' \
      --output text 2>/dev/null || echo "Pending -1")"
    case "$status" in
      Success) info "$label : terminé."; return 0 ;;
      Failed|Cancelled|TimedOut)
        aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$instance_id" \
          --region "$AWS_REGION" --query '[StandardOutputContent,StandardErrorContent]' --output text | tail -30
        fail "$label : échec ($status)"
        ;;
    esac
    sleep 20
    elapsed=$((elapsed + 20))
    echo "  … $label ($status, ${elapsed}s)"
  done
  fail "Timeout commande SSM ($label)"
}

if [[ -n "$WORKER_ID" && "$WORKER_ID" != "null" ]]; then
  wait_ssm_online "$WORKER_ID" "worker"
fi
if [[ -n "$APP_ID" && "$APP_ID" != "null" ]]; then
  wait_ssm_online "$APP_ID" "app"
fi

# cloud-init peut encore builder Docker — attendre puis refresh avec le dernier code
if [[ -n "$WORKER_ID" && "$WORKER_ID" != "null" ]]; then
  info "Déploiement worker (git pull + Docker)…"
  WCMD="$(run_ssm "$WORKER_ID" \
    "cloud-init status --wait 2>/dev/null || true" \
    "cd /opt/clair-obscur && git pull" \
    "bash scripts/ec2-refresh-worker.sh")"
  wait_ssm_command "$WCMD" "$WORKER_ID" "worker"
fi

if [[ -n "$APP_ID" && "$APP_ID" != "null" ]]; then
  info "Déploiement app API + frontend (≈ 5–15 min, build Next.js)…"
  ACMD="$(run_ssm "$APP_ID" \
    "cloud-init status --wait 2>/dev/null || true" \
    "cd /opt/clair-obscur && git pull" \
    "bash scripts/ec2-refresh-app.sh")"
  wait_ssm_command "$ACMD" "$APP_ID" "app"
fi

# --- Health check ---
info "Vérification API…"
elapsed=0
while [[ "$elapsed" -lt 120 ]]; do
  if curl -sf "http://${APP_IP}:8020/health" >/dev/null 2>&1; then
    break
  fi
  sleep 5
  elapsed=$((elapsed + 5))
done

curl -sf "http://${APP_IP}:8020/health" | python3 -m json.tool || warn "API health non disponible — vérifie les logs EC2 app"

# --- Demo upload optionnel ---
if [[ "$INSTALL_UPLOAD_DEMO" == "1" && -f "$ROOT/data/sample_logs/demo.jsonl" ]]; then
  RAW_BUCKET="$(terraform output -raw raw_logs_bucket_name)"
  info "Upload log de démo → s3://${RAW_BUCKET}/…"
  aws s3 cp "$ROOT/data/sample_logs/demo.jsonl" \
    "s3://${RAW_BUCKET}/raw/opensearch/logs-raw/install-demo-$(date +%s).jsonl" \
    --region "$AWS_REGION"
  info "Pipeline déclenchée — nouvelle alerte dans ~1 min sur le dashboard."
fi

# --- Résumé ---
cat <<EOF

${GREEN}════════════════════════════════════════════════════════════${NC}
  CLAIR OBSCUR — installation terminée
${GREEN}════════════════════════════════════════════════════════════${NC}

  Compte AWS     : ${ACCOUNT}
  Région         : ${AWS_REGION}

  Dashboard      : ${FE_URL}/dashboard/alertes
  API            : ${API_URL}
  Health         : ${API_URL}/health

  Worker EC2     : ${WORKER_ID}
  App EC2        : ${APP_ID} (${APP_IP})

  Tester la pipeline :
    aws s3 cp database/multi_alerts_test.jsonl \\
      "s3://$(terraform output -raw raw_logs_bucket_name)/raw/opensearch/logs-raw/test-\$(date +%s).jsonl" \\
      --region ${AWS_REGION} ${AWS_PROFILE:+--profile $AWS_PROFILE}

  Après un git push :
    terraform -chdir=src/terraform output -raw worker_refresh_command | bash
    terraform -chdir=src/terraform output -raw app_refresh_command | bash

${GREEN}════════════════════════════════════════════════════════════${NC}
EOF
