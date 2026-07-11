#!/bin/bash
# git-ref: ${git_ref}
set -euxo pipefail

APP_DIR="/opt/clair-obscur"
ENV_FILE="/etc/clair-obscur/app.env"

ensure_swap() {
  if swapon --show | grep -q /swapfile; then
    return 0
  fi
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
}

dnf install -y docker git docker-compose-plugin
systemctl enable --now docker
usermod -aG docker ec2-user || true
ensure_swap

if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch origin "${git_ref}"
  git -C "$APP_DIR" reset --hard "origin/${git_ref}"
else
  git clone --branch "${git_ref}" --depth 1 "${git_repo_url}" "$APP_DIR"
fi

mkdir -p /etc/clair-obscur
cat > "$ENV_FILE" <<EOF
AWS_REGION=${aws_region}
AWS_DEFAULT_REGION=${aws_region}
RAW_LOGS_BUCKET=${raw_logs_bucket}
RAW_LOGS_PREFIX=${raw_logs_prefix}
PREDICTIONS_BUCKET=${predictions_bucket}
PREDICTIONS_PREFIX=${predictions_prefix}
OUTPUT_BUCKET=${predictions_bucket}
OUTPUT_PREFIX=${predictions_prefix}
DYNAMODB_TABLE=${dynamodb_table}
DYNAMODB_PK=${dynamodb_pk}
ALERTS_SOURCE=s3
BEDROCK_MODEL_ID=${bedrock_model_id}
API_PORT=8020
EOF

chmod +x "$APP_DIR/scripts/ec2-refresh-app.sh"
bash "$APP_DIR/scripts/ec2-refresh-app.sh"

cat > /etc/systemd/system/clair-app.service <<'UNITEOF'
[Unit]
Description=Clair Obscur API + frontend (docker compose prod)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/clair-obscur
ExecStart=/bin/bash /opt/clair-obscur/scripts/ec2-refresh-app.sh

[Install]
WantedBy=multi-user.target
UNITEOF

systemctl daemon-reload
systemctl enable clair-app
