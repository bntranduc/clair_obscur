#!/bin/bash
# VM fraîche : clone du dépôt uniquement (pas d'install agent).
# Tester : sudo /opt/clair-obscur/vm_setup/connect.sh --api-url http://<APP>:8020 --install
# git-ref: ${git_ref}
set -euxo pipefail

APP_DIR="/opt/clair-obscur"

dnf install -y git python3

if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch origin "${git_ref}"
  git -C "$APP_DIR" reset --hard "origin/${git_ref}"
else
  git clone --branch "${git_ref}" --depth 1 "${git_repo_url}" "$APP_DIR"
fi

chmod +x "$APP_DIR/vm_setup/connect.sh" "$APP_DIR/vm_setup/install.sh" 2>/dev/null || true
echo "clair-fresh-vm bootstrap done — run connect.sh manually"
