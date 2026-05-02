"""Prédictions modèle (alertes JSON) dans S3."""

from __future__ import annotations

import json
from typing import Any, Literal
from urllib.parse import unquote

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query

from api import config
from api.deps import s3_client

router = APIRouter(tags=["alerts"])

Pool = Literal["prod", "tmp"]


def _bucket(pool: Pool) -> str:
    if pool == "prod":
        return config.PREDICTIONS_BUCKET
    return config.PREDICTIONS_BUCKET_TMP


def _require_prediction_key(key: str) -> str:
    decoded = unquote(key)
    pfx = config.PREDICTIONS_PREFIX
    if not decoded.startswith(pfx):
        raise HTTPException(
            status_code=400,
            detail=f"key must start with configured prefix {pfx!r}",
        )
    return decoded


@router.get("/s3-objects")
def list_prediction_objects(
    pool: Pool = Query("prod", description="prod ou bucket tmp"),
    max_keys: int = Query(100, ge=1, le=500),
    continuation_token: str | None = None,
) -> dict[str, Any]:
    bucket = _bucket(pool)
    kwargs: dict[str, Any] = {
        "Bucket": bucket,
        "Prefix": config.PREDICTIONS_PREFIX,
        "MaxKeys": max_keys,
    }
    if continuation_token:
        kwargs["ContinuationToken"] = continuation_token
    try:
        r = s3_client().list_objects_v2(**kwargs)
    except ClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    objects: list[dict[str, Any]] = []
    for x in r.get("Contents") or []:
        lm = x.get("LastModified")
        objects.append(
            {
                "key": x["Key"],
                "size": int(x["Size"]),
                "last_modified": lm.isoformat() if lm is not None else None,
            }
        )
    return {
        "pool": pool,
        "bucket": bucket,
        "prefix": config.PREDICTIONS_PREFIX,
        "objects": objects,
        "continuation_token": r.get("NextContinuationToken"),
    }


@router.get("/prediction")
def get_prediction_file(
    pool: Pool = Query("prod"),
    key: str = Query(..., description="Clé S3 du fichier JSON"),
) -> dict[str, Any]:
    bucket = _bucket(pool)
    decoded_key = _require_prediction_key(key)
    try:
        o = s3_client().get_object(Bucket=bucket, Key=decoded_key)
        raw = o["Body"].read().decode("utf-8", errors="replace")
        body = json.loads(raw)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "NoSuchKey":
            raise HTTPException(status_code=404, detail="object not found") from e
        raise HTTPException(status_code=502, detail=str(e)) from e
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"invalid JSON: {e}") from e

    if not isinstance(body, dict):
        raise HTTPException(status_code=502, detail="prediction file must be a JSON object")

    alerts = body.get("alerts")
    if alerts is not None and not isinstance(alerts, list):
        raise HTTPException(status_code=502, detail="alerts must be a list")

    return {
        "pool": pool,
        "bucket": bucket,
        "key": decoded_key,
        "alerts": alerts if isinstance(alerts, list) else [],
        "meta": body.get("meta") if isinstance(body.get("meta"), dict) else None,
    }
