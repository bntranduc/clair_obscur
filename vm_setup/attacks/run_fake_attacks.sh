#!/usr/bin/env bash
# Attaques factices contre la cible locale (nginx) + bruit SSH → logs réels → agent → S3.
set -euo pipefail

PORT="${VM_NGINX_PORT:-8080}"
BASE="http://127.0.0.1:${PORT}"
ATTACKER_IP="${FAKE_ATTACKER_IP:-198.51.100.99}"

echo "==> Attaques application (SQLi, traversal, SSRF) sur ${BASE}"

payloads=(
  "/api?id=1' OR '1'='1"
  "/search?q=1' UNION SELECT username,password FROM users--"
  "/download?file=../../../../etc/passwd"
  "/static/..%2f..%2f..%2fetc/passwd"
  "/fetch?url=http://169.254.169.254/latest/meta-data/"
  "/proxy?target=http://127.0.0.1:6379/"
  "/login?user=admin'--"
  "/report?sort=id' WAITFOR DELAY '0:0:2'--"
)

for uri in "${payloads[@]}"; do
  curl -sf -o /dev/null -w "  %{http_code} ${uri}\n" \
    -H "User-Agent: sqlmap/1.8#stable (fake-attack)" \
    -H "X-Forwarded-For: ${ATTACKER_IP}" \
    "${BASE}${uri}" || true
  sleep 0.3
done

echo "==> Rafale HTTP (brute force simulé)"
for i in $(seq 1 15); do
  curl -sf -o /dev/null \
    -u "user${i}:wrongpass" \
    -H "User-Agent: hydra/9.5" \
    "${BASE}/api?attempt=${i}" || true
done

echo "==> Tentatives SSH locales (auth.log / secure)"
for user in root admin test guest scanner; do
  ssh -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=no \
    "${user}@127.0.0.1" exit 2>/dev/null || true
done

echo "==> Attaques terminées — l'agent enverra les logs sous ~60s."
echo "    Forcer envoi : python3 /opt/clair-vm-agent/ship_logs.py"
