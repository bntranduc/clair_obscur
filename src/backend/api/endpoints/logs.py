"""Logs : lecture depuis S3 (liste d'objets, échantillon JSONL normalisé)."""

from __future__ import annotations

import gzip
import io
import json
from typing import Any
from urllib.parse import unquote

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query

from backend.api import config
from backend.api.deps import s3_client
from backend.log.normalization.normalize import ALL_FIELDS, normalize

router = APIRouter(tags=["logs"])

NORMALIZED_FIELD_ORDER: tuple[str, ...] = (*ALL_FIELDS, "raw_ref")


@router.get("/s3-objects")
def list_log_objects(
    max_keys: int = Query(50, ge=1, le=500),
    continuation_token: str | None = None,
) -> dict[str, Any]:
    """Liste les clés d'objets sous le préfixe brut (partitions dt=/hour=…)."""
    kwargs: dict[str, Any] = {
        "Bucket": config.RAW_BUCKET,
        "Prefix": config.RAW_PREFIX,
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
        "bucket": config.RAW_BUCKET,
        "prefix": config.RAW_PREFIX,
        "objects": objects,
        "continuation_token": r.get("NextContinuationToken"),
    }


@router.get("/s3-sample")
def sample_log_lines(
    key: str = Query(..., description="Clé S3 complète (URL-encodée si besoin)"),
    offset_lines: int = Query(0, ge=0),
    limit_lines: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Lit un fichier JSONL(.gz) OpenSearch : une ligne = un hit ; on expose ``_source`` normalisé."""
    decoded_key = unquote(key)
    if not decoded_key.startswith(config.RAW_PREFIX):
        raise HTTPException(
            status_code=400,
            detail=f"key must start with configured prefix {config.RAW_PREFIX!r}",
        )
    s3 = s3_client()
    try:
        o = s3.get_object(Bucket=config.RAW_BUCKET, Key=decoded_key)
        raw = o["Body"].read()
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "NoSuchKey":
            raise HTTPException(status_code=404, detail="object not found") from e
        raise HTTPException(status_code=502, detail=str(e)) from e

    buf = io.BytesIO(raw)
    if decoded_key.endswith(".gz"):
        gz_stream = gzip.GzipFile(fileobj=buf)
        text_stream = io.TextIOWrapper(gz_stream, encoding="utf-8", errors="replace")
    else:
        text_stream = io.TextIOWrapper(buf, encoding="utf-8", errors="replace")

    logs: list[dict[str, Any]] = []
    truncated_file = False
    stream_line_no = 0
    try:
        for raw_line in text_stream:
            stream_line_no += 1
            if stream_line_no <= offset_lines:
                continue
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "_source" in obj:
                src = obj["_source"]
            elif isinstance(obj, dict):
                src = obj
            else:
                continue
            if not isinstance(src, dict):
                continue
            raw_ref = {"s3_key": decoded_key, "line": stream_line_no}
            logs.append(dict(normalize(src, raw_ref=raw_ref)))
            if len(logs) >= limit_lines:
                truncated_file = True
                break
    finally:
        text_stream.close()

    return {
        "bucket": config.RAW_BUCKET,
        "key": decoded_key,
        "logs": logs,
        "field_order": list(NORMALIZED_FIELD_ORDER),
        "truncated": truncated_file,
        "offset_lines": offset_lines,
        "limit_lines": limit_lines,
    }
