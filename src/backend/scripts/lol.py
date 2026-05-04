import json
import os
import sys
from pathlib import Path

import requests

OS_URL = os.getenv(
    "OPENSEARCH_URL",
    "https://search-hackathon-cnd-pytppy2betrf5qnoqporwcqqbm.eu-west-3.es.amazonaws.com",
)
AUTH = (
    os.getenv("OPENSEARCH_USER", "etudiant"),
    os.getenv("OPENSEARCH_PASSWORD", "HackathonCND2026!"),
)
INDEX = os.getenv("OPENSEARCH_INDEX", "logs-raw")
TIME_FIELD = os.getenv("OPENSEARCH_TIME_FIELD", "timestamp")

# lol.py → …/src/backend/scripts/ → racine repo = 3 niveaux au-dessus
REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_FILE = REPO_ROOT / "logs_opensearch.json"

body = {
    "size": 1000,
    "query": {"match_all": {}},
    "sort": [{TIME_FIELD: {"order": "desc"}}],
}

r = requests.post(
    f"{OS_URL}/{INDEX}/_search",
    auth=AUTH,
    json=body,
    timeout=60,
)

if not r.ok:
    print(r.status_code, r.text[:4000], file=sys.stderr)
    r.raise_for_status()

data = r.json()
hits = data["hits"]["hits"]
logs = [h["_source"] for h in hits]

total = data["hits"].get("total", {})
if isinstance(total, dict):
    total_str = str(total.get("value", total))
else:
    total_str = str(total)

OUT_FILE.write_text(
    json.dumps(logs, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"Récupérés : {len(logs)} (total index : {total_str})")
print(f"Écrit : {OUT_FILE}")