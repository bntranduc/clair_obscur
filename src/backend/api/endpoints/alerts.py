"""Alertes modèle : JSON ``{ alerts, meta? }`` dans S3 (buckets prod / tmp)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query

from backend.api import config
from backend.api.deps import s3_client

# Colonnes tableau alignées sur les hits type DS1 (``serve_app.PredictResponse``).
ALERT_ROW_FIELD_ORDER: tuple[str, ...] = (
    "_id",
    "_index",
    "dataset",
    "challenge_id",
    "attack_type",
    "attacker_ips",
    "victim_accounts",
    "attack_window_start",
    "attack_window_end",
    "indicators",
    "sources_needed",
    "points_max",
)


def _hit_to_row(hit: dict[str, Any]) -> dict[str, Any]:
    src = hit.get("_source") if isinstance(hit.get("_source"), dict) else {}
    aw = src.get("attack_window") if isinstance(src.get("attack_window"), dict) else {}
    return {
        "_id": hit.get("_id"),
        "_index": hit.get("_index"),
        "dataset": src.get("dataset"),
        "challenge_id": src.get("challenge_id"),
        "attack_type": src.get("attack_type"),
        "attacker_ips": src.get("attacker_ips"),
        "victim_accounts": src.get("victim_accounts"),
        "attack_window_start": aw.get("start"),
        "attack_window_end": aw.get("end"),
        "indicators": src.get("indicators"),
        "sources_needed": src.get("sources_needed"),
        "points_max": src.get("points_max"),
    }


def _parse_predictions_payload(raw: bytes) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return [], None
    if not isinstance(data, dict):
        return [], None
    alerts = data.get("alerts")
    meta = data.get("meta")
    if not isinstance(alerts, list):
        alerts = []
    meta_out = meta if isinstance(meta, dict) else None
    hits = [a for a in alerts if isinstance(a, dict)]
    return hits, meta_out


def _ensure_prediction_key(bucket: str, key: str) -> str:
    decoded = unquote(key)
    prefix = config.PREDICTIONS_PREFIX
    if not prefix.endswith("/"):
        prefix = prefix + "/"
    if not decoded.startswith(prefix):
        raise HTTPException(
            status_code=400,
            detail=f"key must start with predictions prefix {prefix!r}",
        )
    return decoded


def _list_objects(bucket: str, max_keys: int, continuation_token: str | None) -> dict[str, Any]:
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
        "bucket": bucket,
        "prefix": config.PREDICTIONS_PREFIX,
        "objects": objects,
        "continuation_token": r.get("NextContinuationToken"),
    }


def _fetch_predictions_file(bucket: str, key: str) -> dict[str, Any]:
    decoded_key = _ensure_prediction_key(bucket, key)
    try:
        o = s3_client().get_object(Bucket=bucket, Key=decoded_key)
        raw = o["Body"].read()
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "NoSuchKey":
            raise HTTPException(status_code=404, detail="object not found") from e
        raise HTTPException(status_code=502, detail=str(e)) from e

    hits, meta = _parse_predictions_payload(raw)
    rows = [_hit_to_row(h) for h in hits]
    return {
        "bucket": bucket,
        "key": decoded_key,
        "meta": meta,
        "alert_count": len(rows),
        "rows": rows,
        "field_order": list(ALERT_ROW_FIELD_ORDER),
    }


router_main = APIRouter()
router_tmp = APIRouter()


@router_main.get("/s3-objects")
def list_main_objects(
    max_keys: int = Query(50, ge=1, le=500),
    continuation_token: str | None = None,
) -> dict[str, Any]:
    return _list_objects(config.PREDICTIONS_BUCKET_MAIN, max_keys, continuation_token)


@router_main.get("/s3-predictions")
def get_main_predictions(
    key: str = Query(..., description="Clé S3 complète du fichier JSON"),
) -> dict[str, Any]:
    return _fetch_predictions_file(config.PREDICTIONS_BUCKET_MAIN, key)


@router_tmp.get("/s3-objects")
def list_tmp_objects(
    max_keys: int = Query(50, ge=1, le=500),
    continuation_token: str | None = None,
) -> dict[str, Any]:
    return _list_objects(config.PREDICTIONS_BUCKET_TMP, max_keys, continuation_token)


@router_tmp.get("/s3-predictions")
def get_tmp_predictions(
    key: str = Query(..., description="Clé S3 complète du fichier JSON"),
) -> dict[str, Any]:
    return _fetch_predictions_file(config.PREDICTIONS_BUCKET_TMP, key)
