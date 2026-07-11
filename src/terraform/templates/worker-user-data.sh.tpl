#!/bin/bash
# git-ref: ${git_ref}
set -euxo pipefail

APP_DIR="/opt/clair-obscur"
ENV_FILE="/etc/clair-obscur/worker.env"
IMAGE="clair-predict-worker:latest"

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

dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user || true
ensure_swap

if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch origin "${git_ref}"
  git -C "$APP_DIR" reset --hard "origin/${git_ref}"
else
  git clone --branch "${git_ref}" --depth 1 "${git_repo_url}" "$APP_DIR"
fi

docker build -f "$APP_DIR/src/backend/worker/Dockerfile" -t "$IMAGE" "$APP_DIR"

mkdir -p /etc/clair-obscur
cat > "$ENV_FILE" <<EOF
AWS_REGION=${aws_region}
AWS_DEFAULT_REGION=${aws_region}
RAW_LOGS_BUCKET=${raw_logs_bucket}
RAW_LOGS_PREFIX=${raw_logs_prefix}
OUTPUT_BUCKET=${predictions_bucket}
OUTPUT_PREFIX=${predictions_prefix}
SQS_QUEUE_URL=${sqs_queue_url}
SQS_VISIBILITY_TIMEOUT=${sqs_visibility_timeout}
PREDICT_MODE=inline
BEDROCK_MODEL_ID=${bedrock_model_id}
BEDROCK_MAX_TOKENS=4096
DYNAMODB_ALERTS_TABLE=${dynamodb_alerts_table}
DYNAMODB_ALERTS_PK=${dynamodb_alerts_pk}
RULES_DEMO_MODE=1
EOF

cat > /etc/systemd/system/clair-predict-worker.service <<'UNITEOF'
[Unit]
Description=Clair Obscur SQS predict worker (Docker)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=simple
Restart=always
RestartSec=15
ExecStartPre=-/usr/bin/docker stop clair-predict-worker
ExecStartPre=-/usr/bin/docker rm clair-predict-worker
ExecStart=/usr/bin/docker run --name clair-predict-worker --env-file /etc/clair-obscur/worker.env clair-predict-worker:latest
ExecStop=/usr/bin/docker stop clair-predict-worker

[Install]
WantedBy=multi-user.target
UNITEOF

systemctl daemon-reload
systemctl enable clair-predict-worker
systemctl restart clair-predict-worker
