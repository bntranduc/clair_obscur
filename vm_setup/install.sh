#!/usr/bin/env bash
# Installe l'agent VM CLAIR OBSCUR (nginx démo + ship_logs → S3).
# Usage :
#   sudo RAW_LOGS_BUCKET=... RAW_LOGS_PREFIX=raw/opensearch/logs-raw/ AWS_REGION=eu-west-3 ./install.sh
#   ou configurer /etc/clair-obscur/vm-agent.env avant install.
set -euo pipefail

VM_SETUP_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="/etc/clair-obscur/vm-agent.env"
AGENT_DIR="/opt/clair-vm-agent"
NGINX_PORT="${VM_NGINX_PORT:-8080}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Relance avec sudo." >&2
  exit 1
fi

if command -v dnf >/dev/null 2>&1; then
  dnf install -y nginx python3 python3-pip
elif command -v apt-get >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y nginx python3 python3-pip python3-venv
else
  echo "OS non supporté (dnf/apt requis)." >&2
  exit 1
fi

mkdir -p /etc/clair-obscur /var/lib/clair-vm-agent
rm -rf "$AGENT_DIR"
cp -a "$VM_SETUP_DIR/agent" "$AGENT_DIR"
python3 -m pip install -q -r "$AGENT_DIR/requirements.txt"

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -n "${RAW_LOGS_BUCKET:-}" ]]; then
    cat > "$ENV_FILE" <<EOF
AWS_REGION=${AWS_REGION:-eu-west-3}
AWS_DEFAULT_REGION=${AWS_REGION:-eu-west-3}
RAW_LOGS_BUCKET=${RAW_LOGS_BUCKET}
RAW_LOGS_PREFIX=${RAW_LOGS_PREFIX:-raw/opensearch/logs-raw/}
VM_ID=${VM_ID:-$(hostname)}
VM_SHIP_INTERVAL_SEC=${VM_SHIP_INTERVAL_SEC:-60}
EOF
  else
    cp "$VM_SETUP_DIR/config/vm-agent.env.example" "$ENV_FILE"
    echo "Édite $ENV_FILE (RAW_LOGS_BUCKET) puis : systemctl restart clair-vm-agent" >&2
  fi
fi

# nginx démo (cible des attaques factices)
install -d -m 755 /usr/share/clair-demo
echo '<html><body><h1>clair demo target</h1></body></html>' > /usr/share/clair-demo/index.html

cat > /etc/nginx/conf.d/clair-demo.conf <<NGINX
server {
    listen ${NGINX_PORT} default_server;
    server_name _;
    access_log /var/log/nginx/access.log combined;
    error_log  /var/log/nginx/error.log warn;
    root /usr/share/clair-demo;
    location / {
        return 200 'ok';
        add_header Content-Type text/plain;
    }
    location /api {
        return 500 'simulated error';
        add_header Content-Type text/plain;
    }
}
NGINX

systemctl enable nginx
systemctl restart nginx

install -m 755 "$VM_SETUP_DIR/attacks/run_fake_attacks.sh" /usr/local/bin/clair-run-fake-attacks

cat > /etc/systemd/system/clair-vm-agent.service <<'UNIT'
[Unit]
Description=Clair Obscur VM log shipper (JSONL → S3)
After=network-online.target nginx.service
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=-/etc/clair-obscur/vm-agent.env
ExecStart=/usr/bin/python3 /opt/clair-vm-agent/ship_logs.py --loop
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable clair-vm-agent
systemctl restart clair-vm-agent

echo ""
echo "Agent VM installé."
echo "  Config   : $ENV_FILE"
echo "  nginx    : http://127.0.0.1:${NGINX_PORT}"
echo "  Attaques : clair-run-fake-attacks"
echo "  Logs     : journalctl -u clair-vm-agent -f"
