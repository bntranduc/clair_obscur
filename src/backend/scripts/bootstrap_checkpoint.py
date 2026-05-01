#!/usr/bin/env python3
"""
Initialise le checkpoint Producer depuis le dernier log présent dans OpenSearch.
À lancer UNE FOIS avant de redémarrer le Producer si le bucket contient déjà des logs.
"""

import base64
import json
import os
import urllib.request
from pathlib import Path
from dotenv import load_dotenv
import boto3

ENV_FILE = Path(__file__).parent.parent / ".env.aws"
load_dotenv(ENV_FILE, override=True)

BUCKET     = os.environ["S3_BUCKET"]
REGION     = os.environ.get("AWS_REGION", "eu-west-3")
OS_URL     = os.environ["OPENSEARCH_URL"]
OS_INDEX   = os.environ["OPENSEARCH_INDEX"]
OS_USER    = os.environ["OPENSEARCH_USER"]
OS_PASS    = os.environ["OPENSEARCH_PASSWORD"]
CHECKPOINT = "_producer_checkpoint/latest.json"

s3 = boto3.client(
    "s3",
    region_name=REGION,
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
)


def os_request(path: str, body: dict) -> dict:
    creds = base64.b64encode(f"{OS_USER}:{OS_PASS}".encode()).decode()
    data  = json.dumps(body).encode()
    req   = urllib.request.Request(
        f"{OS_URL}/{path}",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Basic {creds}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def checkpoint_exists() -> bool:
    try:
        existing = s3.get_object(Bucket=BUCKET, Key=CHECKPOINT)
        content  = json.loads(existing["Body"].read())
        print(f"Checkpoint existant trouvé : {content}")
        print("Rien à faire — le Producer reprendra depuis ce point.")
        return True
    except Exception:
        return False


def bucket_has_logs() -> bool:
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix="logs-raw/", MaxKeys=1)
    return bool(resp.get("Contents"))


def get_last_opensearch_doc() -> tuple[str, str]:
    """Récupère le sort value du dernier document (timestamp le plus récent) en une seule requête."""
    resp = os_request(f"{OS_INDEX}/_search", {
        "size": 1,
        "sort": [{"timestamp": "desc"}, {"_id": "desc"}],
        "_source": False,
    })
    hits = resp["hits"]["hits"]
    if not hits:
        raise RuntimeError("Index OpenSearch vide.")
    sort_vals = hits[0]["sort"]
    return str(sort_vals[0]), str(sort_vals[1])


def main():
    if checkpoint_exists():
        return

    if not bucket_has_logs():
        print("Bucket vide — pas besoin de bootstrap, le Producer partira du début.")
        return

    print("Bucket non vide sans checkpoint détecté.")
    print("Récupération du dernier document OpenSearch...")

    sort_ts, sort_id = get_last_opensearch_doc()
    print(f"Dernier document : timestamp={sort_ts}  _id={sort_id}")

    checkpoint = {"sortTs": sort_ts, "sortId": sort_id, "totalSent": -1}
    s3.put_object(
        Bucket=BUCKET,
        Key=CHECKPOINT,
        Body=json.dumps(checkpoint).encode(),
        ContentType="application/json",
    )
    print(f"Checkpoint écrit dans s3://{BUCKET}/{CHECKPOINT}")
    print("Le Producer ignorera tous les documents déjà ingérés au prochain démarrage.")


if __name__ == "__main__":
    main()
