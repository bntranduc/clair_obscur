"""Charge les alertes depuis les JSON de prédiction S3 (sortie worker)."""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def _s3_client(region: str):
    return boto3.client("s3", region_name=region)


def load_alerts_from_predictions_bucket(
    *,
    bucket: str | None = None,
    prefix: str | None = None,
    region: str | None = None,
    max_files: int = 500,
) -> dict[str, Any]:
    b = (bucket or os.getenv("PREDICTIONS_BUCKET") or os.getenv("OUTPUT_BUCKET") or "").strip()
    if not b:
        raise ValueError("PREDICTIONS_BUCKET ou OUTPUT_BUCKET requis pour ALERTS_SOURCE=s3")
    p = (prefix or os.getenv("PREDICTIONS_PREFIX") or os.getenv("OUTPUT_PREFIX") or "predictions/").strip()
    if not p.endswith("/"):
        p += "/"
    reg = (region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()

    client = _s3_client(reg)
    alerts: list[dict[str, Any]] = []
    n_files = 0
    paginator = client.get_paginator("list_objects_v2")
    try:
        for page in paginator.paginate(Bucket=b, Prefix=p):
            for obj in page.get("Contents") or []:
                key = obj.get("Key") if isinstance(obj, dict) else None
                if not isinstance(key, str) or not key.endswith(".json"):
                    continue
                if "/deploy/" in key:
                    continue
                n_files += 1
                if n_files > max_files:
                    break
                body = client.get_object(Bucket=b, Key=key)["Body"].read()
                try:
                    doc = json.loads(body.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                chunk = doc.get("alerts") if isinstance(doc, dict) else None
                if not isinstance(chunk, list):
                    continue
                meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
                for item in chunk:
                    if not isinstance(item, dict):
                        continue
                    row = dict(item)
                    if meta and "_prediction_meta" not in row:
                        row["_prediction_meta"] = meta
                    row["_prediction_s3_key"] = key
                    alerts.append(row)
            if n_files > max_files:
                break
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"lecture alertes S3 s3://{b}/{p}: {e}") from e

    return {
        "alerts": alerts,
        "count": len(alerts),
        "source": f"s3://{b}/{p}",
        "files_scanned": n_files,
    }
