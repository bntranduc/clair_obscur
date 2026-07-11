#!/bin/bash
# git-ref: ${git_ref}
set -euxo pipefail

APP_DIR="/opt/clair-obscur"
VM_SETUP="/opt/clair-obscur/vm_setup"

dnf install -y git

if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch origin "${git_ref}"
  git -C "$APP_DIR" reset --hard "origin/${git_ref}"
else
  git clone --branch "${git_ref}" --depth 1 "${git_repo_url}" "$APP_DIR"
fi

chmod +x "$VM_SETUP/install.sh" "$VM_SETUP/attacks/run_fake_attacks.sh"

RAW_LOGS_BUCKET=${raw_logs_bucket} \
RAW_LOGS_PREFIX=${raw_logs_prefix} \
AWS_REGION=${aws_region} \
VM_ID=demo-vm \
bash "$VM_SETUP/install.sh"
