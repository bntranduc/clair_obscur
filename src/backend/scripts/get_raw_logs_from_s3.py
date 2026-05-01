import gzip
import json
import os

import boto3

# --- CREDS ---
# Option 1 (recommandé): AWS SSO / aws configure sso, ou variables déjà exportées dans ton shell.
#
# Option 2: exporte ces variables AVANT de lancer le script:
# export AWS_ACCESS_KEY_ID="..."
# export AWS_SECRET_ACCESS_KEY="..."
# export AWS_SESSION_TOKEN="..."   # si creds temporaires (SSO)
# export AWS_DEFAULT_REGION="eu-west-3"

BUCKET = "clair-obscure-raw-logs"
KEY = "raw/opensearch/logs-raw/dt=2026-01-01/hour=01/part-bf43742b-42d8-4636-bdad-86cfd120c450.jsonl.gz"  # <-- remplace
N = 20

# Si besoin de forcer la région:
REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")
s3 = boto3.client("s3", region_name=REGION)

obj = s3.get_object(Bucket=BUCKET, Key=KEY)

for i, line in enumerate(gzip.decompress(obj["Body"].read()).splitlines()):
    if i >= N:
        break
    rec = json.loads(line)
    print(json.dumps(rec.get("_source", rec), ensure_ascii=False))