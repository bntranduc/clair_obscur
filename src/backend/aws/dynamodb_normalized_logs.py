"""Lecture paginée des logs normalisés stockés dans DynamoDB (table ``pk`` / ``sk``).

Chaîne d’identifiants : même logique que ``test.py`` (``AWS_PROFILE``, ou clés ``AWS_*`` dans l’env).
"""

from __future__ import annotations

import base64
import json
import os
from decimal import Decimal
from typing import Any

import boto3


def _aws_session(region: str) -> boto3.Session:
    """Aligné sur ``test.py`` : profil ou clés explicites."""
    # Comme ``AwsClient.session`` : boto3/botocore lit ``AWS_PROFILE`` même sans ``profile_name`` ;
    # une valeur vide → ProfileNotFound (profil "").
    _ap = os.environ.get("AWS_PROFILE")
    if _ap is not None and not str(_ap).strip():
        del os.environ["AWS_PROFILE"]

    ak = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
    sk = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
    st = (os.getenv("AWS_SESSION_TOKEN") or "").strip() or None
    profile = (os.getenv("AWS_PROFILE") or "").strip() or None
    if ak and sk:
        return boto3.Session(
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            aws_session_token=st,
            region_name=region,
        )
    if profile:
        return boto3.Session(profile_name=profile, region_name=region)
    return boto3.Session(region_name=region)


def _jsonify_for_api(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: _jsonify_for_api(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonify_for_api(v) for v in obj]
    return obj


def _encode_start_key(lek: dict[str, Any]) -> str:
    """Encode ``LastEvaluatedKey`` minimal (pk + sk) pour l’URL."""
    payload = {"pk": lek["pk"], "sk": lek["sk"]}
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_start_key(cursor: str) -> dict[str, str]:
    pad = (-len(cursor)) % 4
    raw = base64.urlsafe_b64decode(cursor.encode("ascii") + b"=" * pad)
    d = json.loads(raw.decode("utf-8"))
    if not isinstance(d, dict) or "pk" not in d or "sk" not in d:
        raise ValueError("start_key invalide")
    return {"pk": str(d["pk"]), "sk": str(d["sk"])}


def default_logs_partition_key() -> str:
    """Partition par défaut — alignée sur ``test.py`` (``DYNAMODB_PK`` / démo 2026-01-12)."""
    full = (os.getenv("DYNAMODB_LOGS_PK") or os.getenv("DYNAMODB_PK") or "").strip()
    if full:
        return full
    bucket = os.getenv("RAW_LOGS_BUCKET", "clair-obscure-raw-logs").strip()
    day = (os.getenv("DYNAMODB_LOGS_DAY") or "").strip()
    if day:
        return f"RAW#{bucket}#D#{day}"
    return (os.getenv("DYNAMODB_LOGS_DEFAULT_PK") or "RAW#clair-obscure-raw-logs#D#2026-01-12").strip()


def fetch_normalized_page_from_dynamodb(
    *,
    pk: str,
    limit: int = 50,
    start_key: str | None = None,
    region: str | None = None,
    table_name: str | None = None,
) -> tuple[list[dict[str, Any]], bool, str | None]:
    """Retourne ``(items, has_more, next_start_key)`` — ``items`` au format proche ``NormalizedEvent`` + ``id``."""
    reg = (region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()
    table = (table_name or os.getenv("DYNAMODB_TABLE", "normalized-logs")).strip()
    if limit < 1:
        limit = 1

    session = _aws_session(reg)
    tbl = session.resource("dynamodb", region_name=reg).Table(table)

    kwargs: dict[str, Any] = {
        "KeyConditionExpression": "pk = :p",
        "ExpressionAttributeValues": {":p": pk},
        "ScanIndexForward": False,
        "Limit": limit,
    }
    if start_key and start_key.strip():
        kwargs["ExclusiveStartKey"] = _decode_start_key(start_key.strip())

    resp = tbl.query(**kwargs)
    raw_items = resp.get("Items") or []
    out: list[dict[str, Any]] = []
    for it in raw_items:
        event = it.get("event") if isinstance(it.get("event"), dict) else {}
        row = dict(event)
        if "id" in it and it["id"] is not None:
            row["id"] = it["id"]
        out.append(_jsonify_for_api(row))

    lek = resp.get("LastEvaluatedKey")
    has_more = lek is not None
    next_cursor = _encode_start_key(lek) if lek else None
    return out, has_more, next_cursor
