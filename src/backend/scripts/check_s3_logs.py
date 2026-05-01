#!/usr/bin/env python3
"""Vérifie le flux Kafka→S3 : nombre total de logs et 3 derniers."""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import boto3

ENV_FILE = Path(__file__).parent.parent / ".env.aws"
load_dotenv(ENV_FILE, override=True)

BUCKET = os.environ["S3_BUCKET"]
REGION = os.environ.get("AWS_REGION", "eu-west-3")
PREFIX = "logs-raw/"
FLUSH_SIZE = 1000  # flushSize défini dans S3RawLogSink

s3 = boto3.client(
    "s3",
    region_name=REGION,
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
)


def list_all_files() -> list[dict]:
    paginator = s3.get_paginator("list_objects_v2")
    objects = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        objects.extend(page.get("Contents", []))
    return sorted(objects, key=lambda o: o["LastModified"], reverse=True)


def count_logs(files: list[dict]) -> int:
    """Compte exact : chaque fichier complet = FLUSH_SIZE lignes exactement.
    Seul le dernier fichier peut être incomplet (flush de close()) — on le télécharge."""
    if not files:
        return 0
    last = files[0]  # le plus récent, potentiellement incomplet
    body = s3.get_object(Bucket=BUCKET, Key=last["Key"])["Body"].read().decode()
    last_count = sum(1 for line in body.splitlines() if line.strip())
    return (len(files) - 1) * FLUSH_SIZE + last_count


def fetch_last_n_logs(files: list[dict], n: int = 3) -> list[dict]:
    logs = []
    for obj in files:
        if len(logs) >= n:
            break
        body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read().decode()
        lines = [l for l in body.splitlines() if l.strip()]
        if lines:
            logs.append({
                "file": obj["Key"],
                "modified": obj["LastModified"].isoformat(),
                "log": json.loads(lines[-1]),
            })
    return logs[:n]


def main():
    print(f"Bucket : s3://{BUCKET}/{PREFIX}")
    print(f"Région : {REGION}")
    print()

    try:
        all_files = list_all_files()
    except Exception as e:
        print(f"Erreur de connexion S3 : {e}", file=sys.stderr)
        sys.exit(1)

    if not all_files:
        print("Aucun fichier trouvé sous logs-raw/")
        print("→ Le Consumer n'a pas encore écrit dans S3 (attendre le premier flush de 1000 logs).")
        sys.exit(0)

    total = count_logs(all_files)
    print(f"Fichiers : {len(all_files)}")
    print(f"Logs     : {total:,} (exact)")
    print()

    logs = fetch_last_n_logs(all_files, n=3)
    for i, entry in enumerate(logs, 1):
        print(f"── Log {i} ─────────────────────────────────")
        print(f"  Fichier  : {entry['file']}")
        print(f"  Modifié  : {entry['modified']}")
        print(f"  Contenu  :")
        print(json.dumps(entry["log"], indent=4, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
