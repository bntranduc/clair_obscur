#!/usr/bin/env bash
# Rafale d'attaques factices depuis ton laptop vers la VM démo.
# Envoie assez de requêtes pour déclencher SQLi, SSRF, traversal, brute force.
#
# Usage : DEMO=15.237.60.67 ./run_from_laptop.sh
set -euo pipefail

DEMO="${DEMO:-15.237.60.67}"
BASE="http://${DEMO}:8080"

echo "==> Rafale multi-attaques sur ${BASE}"

# SQLi (≥3 patterns recommandé)
for i in 1 2 3; do
  curl -sG "${BASE}/api" -H 'User-Agent: sqlmap/1.8#stable' \
    --data-urlencode "id=1' OR '1'='1" -o /dev/null -w "  sqli[$i]=%{http_code}\n" || true
done
curl -sf -o /dev/null -w "  sqli[union]=%{http_code}\n" \
  -H 'User-Agent: sqlmap/1.8#stable' \
  "${BASE}/search?q=1%27%20UNION%20SELECT%20username,password%20FROM%20users--" || true

# Directory traversal
curl -sf -o /dev/null -w "  traversal=%{http_code}\n" \
  "${BASE}/download?file=../../../../etc/passwd" || true
curl -sf -o /dev/null -w "  traversal2=%{http_code}\n" \
  "${BASE}/static/..%2f..%2f..%2fetc/passwd" || true

# SSRF (≥3 requêtes)
for target in \
  "http://169.254.169.254/latest/meta-data/" \
  "http://127.0.0.1:6379/" \
  "http://127.0.0.1:9200/"; do
  curl -sf -o /dev/null -w "  ssrf=%{http_code} ${target}\n" \
    "${BASE}/fetch?url=${target}" || true
done

# Brute force HTTP simulé
for i in $(seq 1 15); do
  curl -sf -o /dev/null -u "user${i}:wrongpass" \
    "${BASE}/api?attempt=${i}" || true
done

echo ""
echo "==> Attaques envoyées. Attends ~2 min puis vérifie le dashboard alertes."
echo "    Forcer envoi logs sur la VM : terraform -chdir=src/terraform output -raw demo_vm_run_attacks_command | bash"
