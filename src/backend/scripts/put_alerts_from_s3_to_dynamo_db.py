#!/usr/bin/env python3
"""
Backfill : parcourt les JSON de prédiction S3 et écrit les alertes dans DynamoDB.

Usage (racine du repo) :
  set -a && source .env && set +a
  PYTHONPATH=src python3 src/backend/scripts/put_alerts_from_s3_to_dynamo_db.py
"""
from __future__ import annotations

import json
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, os.path.join(_REPO, "src"))

import boto3
from backend.aws.dynamodb_alerts import put_alerts_to_dynamodb

BUCKET = (
    os.getenv("PREDICTIONS_BUCKET") or os.getenv("OUTPUT_BUCKET") or ""
).strip()
PREFIX = (os.getenv("PREDICTIONS_PREFIX") or os.getenv("OUTPUT_PREFIX") or "predictions/").strip()
if not PREFIX.endswith("/"):
    PREFIX += "/"
REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
DRY_RUN = os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}


def main() -> None:
    if not BUCKET:
        print("PREDICTIONS_BUCKET ou OUTPUT_BUCKET requis", file=sys.stderr)
        sys.exit(1)

    s3 = boto3.client("s3", region_name=REGION)
    n_files = 0
    n_alerts = 0

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents") or []:
            key = obj.get("Key") if isinstance(obj, dict) else None
            if not isinstance(key, str) or not key.endswith(".json") or "/deploy/" in key:
                continue
            n_files += 1
            body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
            try:
                doc = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            alerts = doc.get("alerts") if isinstance(doc, dict) else None
            meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
            if not isinstance(alerts, list) or not alerts:
                continue
            if DRY_RUN:
                n_alerts += len(alerts)
                if n_files <= 3:
                    print(f"DRY_RUN {key} alerts={len(alerts)}")
                continue
            n_alerts += put_alerts_to_dynamodb(
                alerts,
                meta=meta,
                prediction_s3_key=key,
                region=REGION,
            )

    print(f"Terminé : {n_files} fichiers, {n_alerts} alertes écrites (DRY_RUN={DRY_RUN})")


if __name__ == "__main__":
    main()
