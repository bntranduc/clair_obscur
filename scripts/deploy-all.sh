#!/usr/bin/env bash
# Déploiement complet CLAIR OBSCUR depuis zéro (compte AWS vierge + prérequis).
#
# Usage :
#   cp .env.example .env    # credentials AWS + GIT_REPO_URL
#   ./deploy-all.sh
#
# À la fin : URL du dashboard affichée.
set -euo pipefail

DEPLOY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_TF_DIR="$DEPLOY_ROOT/src/terraform"
DEPLOY_ENV_FILE="$DEPLOY_ROOT/.env"

# shellcheck source=scripts/lib/deploy-common.sh
source "$DEPLOY_ROOT/scripts/lib/deploy-common.sh"

main() {
  print_prerequisites_banner
  load_env_file
  check_binaries
  check_aws_credentials
  check_default_vpc
  check_bedrock_access
  check_git_remote
  generate_tfvars
  run_terraform_apply
  sync_env_from_terraform
  deploy_ec2_instances
  verify_app_health
  upload_demo_log
  maybe_upload_log_llm
  maybe_push_openrouter
  print_deployment_summary
}

main "$@"
