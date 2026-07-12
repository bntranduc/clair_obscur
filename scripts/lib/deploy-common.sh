#!/usr/bin/env bash
# Bibliothèque partagée pour deploy-all.sh / install.sh
set -euo pipefail

: "${DEPLOY_ROOT:?DEPLOY_ROOT must be set}"
: "${DEPLOY_TF_DIR:?DEPLOY_TF_DIR must be set}"
: "${DEPLOY_ENV_FILE:?DEPLOY_ENV_FILE must be set}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}==>${NC} $*"; }
fail()  { echo -e "${RED}Erreur:${NC} $*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Commande « $1 » introuvable."
}

load_env_file() {
  if [[ ! -f "$DEPLOY_ENV_FILE" ]]; then
    cp "$DEPLOY_ROOT/.env.example" "$DEPLOY_ENV_FILE"
    fail "Créé $DEPLOY_ENV_FILE — renseigne AWS + GIT_REPO_URL puis relance ./deploy-all.sh"
  fi
  set -a
  # shellcheck disable=SC1090
  source "$DEPLOY_ENV_FILE"
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
  DEMO_VM_INSTANCE_TYPE="${DEMO_VM_INSTANCE_TYPE:-t3.micro}"
  ENABLE_EC2_WORKER="${ENABLE_EC2_WORKER:-1}"
  ENABLE_EC2_APP="${ENABLE_EC2_APP:-1}"
  ENABLE_EC2_DEMO_VM="${ENABLE_EC2_DEMO_VM:-1}"
  ENABLE_EC2_FRESH_VM="${ENABLE_EC2_FRESH_VM:-0}"
  INSTALL_UPLOAD_DEMO="${INSTALL_UPLOAD_DEMO:-1}"
  INSTALL_GIT_PUSH="${INSTALL_GIT_PUSH:-0}"
  INSTALL_WAIT_TIMEOUT="${INSTALL_WAIT_TIMEOUT:-2400}"
  DEPLOY_OPENROUTER="${DEPLOY_OPENROUTER:-auto}"
  DEPLOY_LOG_LLM="${DEPLOY_LOG_LLM:-auto}"
}

check_binaries() {
  info "Vérification des binaires…"
  need_cmd aws
  need_cmd terraform
  need_cmd git
  need_cmd python3
  need_cmd curl
}

check_aws_credentials() {
  info "Vérification credentials AWS (région $AWS_REGION)…"
  if ! IDENTITY="$(aws sts get-caller-identity --output json 2>/dev/null)"; then
    cat >&2 <<EOF
${RED}Credentials AWS invalides.${NC}

1. Crée un utilisateur IAM avec AdministratorAccess
2. aws configure --profile clair-obscur   (ou mets AWS_ACCESS_KEY_ID/SECRET dans .env)
3. Dans .env : AWS_PROFILE=clair-obscur  et  AWS_REGION=eu-west-3

EOF
    exit 1
  fi
  DEPLOY_ACCOUNT="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])' <<< "$IDENTITY")"
  info "Compte AWS : $DEPLOY_ACCOUNT"
}

check_default_vpc() {
  info "Vérification VPC par défaut…"
  local vpc_id
  vpc_id="$(aws ec2 describe-vpcs \
    --filters Name=isDefault,Values=true \
    --region "$AWS_REGION" \
    --query 'Vpcs[0].VpcId' \
    --output text 2>/dev/null || echo "None")"
  if [[ -z "$vpc_id" || "$vpc_id" == "None" ]]; then
    fail "Aucun VPC par défaut dans $AWS_REGION. Crée-en un (console EC2 → VPC) ou utilise une région avec default VPC."
  fi
  local subnet_count
  subnet_count="$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$vpc_id" \
    --region "$AWS_REGION" \
    --query 'length(Subnets)' \
    --output text)"
  if [[ "$subnet_count" == "0" ]]; then
    fail "VPC $vpc_id sans subnet — ajoute au moins un subnet public."
  fi
  info "VPC par défaut : $vpc_id ($subnet_count subnet(s))"
}

check_bedrock_access() {
  info "Vérification Bedrock ($BEDROCK_MODEL_ID)…"
  if aws bedrock get-foundation-model \
    --model-identifier "$BEDROCK_MODEL_ID" \
    --region "$AWS_REGION" >/dev/null 2>&1; then
    info "Modèle Bedrock accessible."
    return 0
  fi
  cat <<EOF

${YELLOW}Prérequis manuel — activer Bedrock :${NC}
  Console AWS → Amazon Bedrock → Model access (ou Playground)
  Région : ${AWS_REGION}
  Modèle : ${BEDROCK_MODEL_ID}

Puis relance : ./deploy-all.sh

EOF
  exit 1
}

check_git_remote() {
  info "Dépôt EC2 : $GIT_REPO_URL (ref: $GIT_REF)"
  if ! git -C "$DEPLOY_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    return 0
  fi
  local ahead
  ahead="$(git -C "$DEPLOY_ROOT" rev-list --count "@{u}..HEAD" 2>/dev/null || echo 0)"
  if [[ "$ahead" -gt 0 ]]; then
    warn "$ahead commit(s) local(aux) non poussé(s)."
    if [[ "$INSTALL_GIT_PUSH" == "1" ]]; then
      info "Push origin/${GIT_REF}…"
      git -C "$DEPLOY_ROOT" push origin "HEAD:${GIT_REF}"
    else
      warn "Les EC2 cloneront le code distant — pousse avec git push ou INSTALL_GIT_PUSH=1"
    fi
  fi
}

tf_bool() {
  [[ "$1" == "1" || "$1" == "true" || "$1" == "yes" ]] && echo true || echo false
}

generate_tfvars() {
  local tf_profile="${AWS_PROFILE:-clair-obscur}"
  if [[ -n "${AWS_ACCESS_KEY_ID:-}" && -z "${AWS_PROFILE:-}" ]]; then
    tf_profile=""
  fi
  info "Génération $DEPLOY_TF_DIR/terraform.tfvars"
  cat > "$DEPLOY_TF_DIR/terraform.tfvars" <<EOF
aws_region   = "${AWS_REGION}"
aws_profile  = "${tf_profile}"
project_name = "clair-obscur"
environment  = "dev"

force_destroy = true

raw_logs_prefix    = "raw/opensearch/logs-raw"
predictions_prefix   = "predictions"
enable_versioning    = true

dynamodb_demo_day = "2026-01-12"

worker_instance_type    = "${WORKER_INSTANCE_TYPE}"
worker_git_repo_url     = "${GIT_REPO_URL}"
worker_git_ref          = "${GIT_REF}"
worker_bedrock_model_id = "${BEDROCK_MODEL_ID}"

enable_ec2_worker = $(tf_bool "$ENABLE_EC2_WORKER")
enable_ec2_app    = $(tf_bool "$ENABLE_EC2_APP")
app_instance_type = "${APP_INSTANCE_TYPE}"

enable_ec2_demo_vm    = $(tf_bool "$ENABLE_EC2_DEMO_VM")
demo_vm_instance_type = "${DEMO_VM_INSTANCE_TYPE}"

enable_ec2_fresh_vm    = $(tf_bool "$ENABLE_EC2_FRESH_VM")
fresh_vm_instance_type = "t3.micro"
EOF
}

run_terraform_apply() {
  info "Terraform init + apply (≈ 3–8 min)…"
  cd "$DEPLOY_TF_DIR"
  terraform init -input=false
  terraform validate
  terraform apply -auto-approve
}

sync_env_from_terraform() {
  local snippet
  snippet="$(terraform -chdir="$DEPLOY_TF_DIR" output -raw env_snippet)"
  info "Mise à jour $DEPLOY_ENV_FILE"
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    local key="${line%%=*}"
    if grep -q "^${key}=" "$DEPLOY_ENV_FILE" 2>/dev/null; then
      sed -i "s|^${key}=.*|${line}|" "$DEPLOY_ENV_FILE"
    else
      printf '\n%s\n' "$line" >> "$DEPLOY_ENV_FILE"
    fi
  done <<< "$snippet"

  local log_uri
  log_uri="$(terraform -chdir="$DEPLOY_TF_DIR" output -raw log_llm_model_s3_uri 2>/dev/null || true)"
  if [[ -n "$log_uri" && "$log_uri" != "null" ]]; then
    if grep -q '^LOG_LLM_MODEL_S3_URI=' "$DEPLOY_ENV_FILE" 2>/dev/null; then
      sed -i "s|^LOG_LLM_MODEL_S3_URI=.*|LOG_LLM_MODEL_S3_URI=${log_uri}|" "$DEPLOY_ENV_FILE"
    else
      echo "LOG_LLM_MODEL_S3_URI=${log_uri}" >> "$DEPLOY_ENV_FILE"
    fi
  fi

  for kv in "GIT_REPO_URL=${GIT_REPO_URL}" "GIT_REF=${GIT_REF}"; do
    key="${kv%%=*}"
    if grep -q "^${key}=" "$DEPLOY_ENV_FILE" 2>/dev/null; then
      sed -i "s|^${key}=.*|${kv}|" "$DEPLOY_ENV_FILE"
    else
      echo "$kv" >> "$DEPLOY_ENV_FILE"
    fi
  done
}

wait_ssm_online() {
  local id="$1" label="$2"
  local elapsed=0
  info "Attente SSM ($label: $id)…"
  while [[ "$elapsed" -lt "$INSTALL_WAIT_TIMEOUT" ]]; do
    local status
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
    --timeout-seconds "$INSTALL_WAIT_TIMEOUT" \
    --parameters "commands=${json}" \
    --region "$AWS_REGION" \
    --query Command.CommandId \
    --output text
}

wait_ssm_command() {
  local cmd_id="$1" instance_id="$2" label="$3"
  local elapsed=0
  while [[ "$elapsed" -lt "$INSTALL_WAIT_TIMEOUT" ]]; do
    local status code
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
          --region "$AWS_REGION" --query '[StandardOutputContent,StandardErrorContent]' --output text | tail -40
        fail "$label : échec ($status)"
        ;;
    esac
    sleep 20
    elapsed=$((elapsed + 20))
    echo "  … $label ($status, ${elapsed}s)"
  done
  fail "Timeout commande SSM ($label)"
}

ec2_git_sync_cmd() {
  printf 'cd /opt/clair-obscur && git fetch origin %s && git reset --hard origin/%s' "$GIT_REF" "$GIT_REF"
}

deploy_ec2_instances() {
  DEPLOY_APP_ID="$(terraform -chdir="$DEPLOY_TF_DIR" output -raw app_instance_id 2>/dev/null || true)"
  DEPLOY_WORKER_ID="$(terraform -chdir="$DEPLOY_TF_DIR" output -raw predict_worker_instance_id 2>/dev/null || true)"

  if [[ -n "$DEPLOY_WORKER_ID" && "$DEPLOY_WORKER_ID" != "null" ]]; then
    wait_ssm_online "$DEPLOY_WORKER_ID" "worker"
  fi
  if [[ -n "$DEPLOY_APP_ID" && "$DEPLOY_APP_ID" != "null" ]]; then
    wait_ssm_online "$DEPLOY_APP_ID" "app"
  fi

  local git_sync
  git_sync="$(ec2_git_sync_cmd)"

  if [[ -n "$DEPLOY_WORKER_ID" && "$DEPLOY_WORKER_ID" != "null" ]]; then
    info "Déploiement worker (Docker)…"
    local wcmd
    wcmd="$(run_ssm "$DEPLOY_WORKER_ID" \
      "cloud-init status --wait 2>/dev/null || true" \
      "$git_sync" \
      "bash scripts/ec2-refresh-worker.sh")"
    wait_ssm_command "$wcmd" "$DEPLOY_WORKER_ID" "worker"
  fi

  if [[ -n "$DEPLOY_APP_ID" && "$DEPLOY_APP_ID" != "null" ]]; then
    info "Déploiement app API + frontend (≈ 5–20 min)…"
    local acmd
    acmd="$(run_ssm "$DEPLOY_APP_ID" \
      "cloud-init status --wait 2>/dev/null || true" \
      "$git_sync" \
      "bash scripts/ec2-refresh-app.sh")"
    wait_ssm_command "$acmd" "$DEPLOY_APP_ID" "app"
  fi
}

verify_app_health() {
  DEPLOY_APP_IP="$(terraform -chdir="$DEPLOY_TF_DIR" output -raw app_public_ip 2>/dev/null || true)"
  DEPLOY_API_URL="$(terraform -chdir="$DEPLOY_TF_DIR" output -raw app_api_url 2>/dev/null || true)"
  DEPLOY_FE_URL="$(terraform -chdir="$DEPLOY_TF_DIR" output -raw app_frontend_url 2>/dev/null || true)"

  [[ -n "$DEPLOY_APP_IP" && "$DEPLOY_APP_IP" != "null" ]] || fail "app_public_ip introuvable après apply."

  info "Vérification API http://${DEPLOY_APP_IP}:8020/health …"
  local elapsed=0
  while [[ "$elapsed" -lt 180 ]]; do
    if curl -sf "http://${DEPLOY_APP_IP}:8020/health" >/dev/null 2>&1; then
      curl -sf "http://${DEPLOY_APP_IP}:8020/health" | python3 -m json.tool
      return 0
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  fail "API health non disponible sur ${DEPLOY_API_URL}/health"
}

upload_demo_log() {
  if [[ "$INSTALL_UPLOAD_DEMO" != "1" ]]; then
    return 0
  fi
  local demo_file="$DEPLOY_ROOT/data/sample_logs/demo.jsonl"
  [[ -f "$demo_file" ]] || { warn "Pas de $demo_file — skip demo upload."; return 0; }
  local raw_bucket
  raw_bucket="$(terraform -chdir="$DEPLOY_TF_DIR" output -raw raw_logs_bucket_name)"
  info "Upload log démo → s3://${raw_bucket}/…"
  aws s3 cp "$demo_file" \
    "s3://${raw_bucket}/raw/opensearch/logs-raw/install-demo-$(date +%s).jsonl" \
    --region "$AWS_REGION"
  info "Pipeline SQS déclenchée — alerte attendue sous ~1 min."
}

maybe_upload_log_llm() {
  local ckpt="$DEPLOY_ROOT/src/llm_from_scratch/model_prod/ckpt.pt"
  if [[ "$DEPLOY_LOG_LLM" == "0" || "$DEPLOY_LOG_LLM" == "false" ]]; then
    return 0
  fi
  if [[ ! -f "$ckpt" ]]; then
    if [[ "$DEPLOY_LOG_LLM" == "auto" ]]; then
      warn "Pas de checkpoint Log LLM local — skip upload S3."
      return 0
    fi
    fail "DEPLOY_LOG_LLM=1 mais $ckpt introuvable."
  fi
  info "Upload checkpoint Log LLM vers S3…"
  bash "$DEPLOY_ROOT/scripts/upload-log-llm-model.sh"
  if [[ -n "${DEPLOY_APP_ID:-}" && "$DEPLOY_APP_ID" != "null" ]]; then
    info "Refresh app (sync modèle + container explain)…"
    local acmd
    acmd="$(run_ssm "$DEPLOY_APP_ID" \
      "$(ec2_git_sync_cmd)" \
      "bash scripts/ec2-refresh-app.sh")"
    wait_ssm_command "$acmd" "$DEPLOY_APP_ID" "app-log-llm"
  fi
}

maybe_push_openrouter() {
  local key_file="${OPENROUTER_KEY_FILE:-$DEPLOY_ROOT/openrout_key.txt}"
  local do_push=0
  if [[ "$DEPLOY_OPENROUTER" == "1" || "$DEPLOY_OPENROUTER" == "true" ]]; then
    do_push=1
  elif [[ "$DEPLOY_OPENROUTER" == "auto" && ( -n "${OPENROUTER_API_KEY:-}" || -f "$key_file" ) ]]; then
    do_push=1
  fi
  [[ "$do_push" -eq 1 ]] || return 0
  info "Déploiement clé OpenRouter sur EC2 app…"
  if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
    local tmp
    tmp="$(mktemp)"
    printf '%s' "$OPENROUTER_API_KEY" > "$tmp"
    bash "$DEPLOY_ROOT/scripts/ec2-push-secrets.sh" "$tmp"
    rm -f "$tmp"
  else
    bash "$DEPLOY_ROOT/scripts/ec2-push-secrets.sh" "$key_file"
  fi
}

print_deployment_summary() {
  local summary
  summary="$(terraform -chdir="$DEPLOY_TF_DIR" output -json deployment_summary 2>/dev/null || echo "{}")"
  local dash api health
  dash="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("dashboard_url",""))' <<< "$summary")"
  api="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("api_url",""))' <<< "$summary")"
  health="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("health_url",""))' <<< "$summary")"
  local alerts="${dash}/dashboard/alertes"
  local chat="${dash}/dashboard/chat"

  cat <<EOF

${GREEN}════════════════════════════════════════════════════════════${NC}
  ${CYAN}CLAIR OBSCUR — déploiement terminé${NC}
${GREEN}════════════════════════════════════════════════════════════${NC}

  Compte AWS     : ${DEPLOY_ACCOUNT}
  Région         : ${AWS_REGION}

  ${CYAN}→ Dashboard${NC}    : ${dash}
  ${CYAN}→ Alertes${NC}      : ${alerts}
  ${CYAN}→ Assistant IA${NC} : ${chat}
  API            : ${api}
  Health         : ${health}

  Worker EC2     : ${DEPLOY_WORKER_ID:-—}
  App EC2        : ${DEPLOY_APP_ID:-—} (${DEPLOY_APP_IP:-—})

  Après un git push :
    terraform -chdir=src/terraform output -raw app_refresh_command | bash

  Optionnel :
    OpenRouter     : OPENROUTER_API_KEY dans .env puis ./deploy-all.sh
    Log LLM local  : model_prod/ckpt.pt + DEPLOY_LOG_LLM=1 ./deploy-all.sh

${GREEN}════════════════════════════════════════════════════════════${NC}
EOF
}

print_prerequisites_banner() {
  cat <<EOF
${CYAN}Prérequis (compte AWS vierge) :${NC}
  1. Utilisateur IAM avec ${GREEN}AdministratorAccess${NC}
  2. Credentials dans .env (AWS_PROFILE ou ACCESS_KEY)
  3. Bedrock : activer ${BEDROCK_MODEL_ID} en ${AWS_REGION}
  4. GIT_REPO_URL accessible depuis EC2 (repo public ou token dans l'URL)
  5. Terraform ≥ 1.5, AWS CLI v2, git, curl, python3

EOF
}
