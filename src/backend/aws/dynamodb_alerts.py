"""Lecture / écriture des alertes dans DynamoDB (table ``pk`` / ``sk``)."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

from backend.aws.dynamodb_normalized_logs import _aws_session, _jsonify_for_api


def default_alerts_partition_key() -> str:
    return (os.getenv("DYNAMODB_ALERTS_PK") or "ALERTS").strip() or "ALERTS"


def default_alerts_table_name() -> str:
    return (os.getenv("DYNAMODB_ALERTS_TABLE") or "alerts").strip() or "alerts"


def _ddb_document(v: Any) -> Any:
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, dict):
        return {k: _ddb_document(x) for k, x in v.items() if x is not None}
    if isinstance(v, list):
        return [_ddb_document(x) for x in v if x is not None]
    return v


def _alert_sort_key(
    alert: dict[str, Any],
    *,
    prediction_s3_key: str,
) -> str:
    detection = alert.get("detection") if isinstance(alert.get("detection"), dict) else {}
    ts = (
        (detection.get("attack_start_time") if isinstance(detection.get("attack_start_time"), str) else None)
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    challenge_id = str(alert.get("challenge_id") or "unknown")
    h = hashlib.sha256(prediction_s3_key.encode()).hexdigest()[:12]
    return f"{ts}#{challenge_id}#{h}"


def put_alerts_to_dynamodb(
    alerts: list[dict[str, Any]],
    *,
    meta: dict[str, Any],
    prediction_s3_key: str,
    region: str | None = None,
    table_name: str | None = None,
    pk: str | None = None,
) -> int:
    """Écrit les alertes d'une prédiction worker. Retourne le nombre d'items écrits."""
    if not alerts:
        return 0

    reg = (region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()
    table = (table_name or default_alerts_table_name()).strip()
    partition = (pk or default_alerts_partition_key()).strip()
    tbl = _aws_session(reg).resource("dynamodb", region_name=reg).Table(table)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n = 0

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        item = {
            "pk": partition,
            "sk": _alert_sort_key(alert, prediction_s3_key=prediction_s3_key),
            "challenge_id": str(alert.get("challenge_id") or ""),
            "severity": str(alert.get("severity") or ""),
            "alert": _ddb_document(dict(alert)),
            "prediction_s3_key": prediction_s3_key,
            "source_bucket": str(meta.get("source_bucket") or ""),
            "source_key": str(meta.get("source_key") or ""),
            "created_at": created_at,
        }
        tbl.put_item(Item=item)
        n += 1
    return n


def load_all_alerts_from_dynamodb(
    *,
    pk: str | None = None,
    max_items: int = 1000,
    region: str | None = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """Query toutes les alertes sous la partition ``ALERTS`` (ou ``DYNAMODB_ALERTS_PK``)."""
    reg = (region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()
    table = (table_name or default_alerts_table_name()).strip()
    partition = (pk or default_alerts_partition_key()).strip()
    if max_items < 1:
        max_items = 1

    tbl = _aws_session(reg).resource("dynamodb", region_name=reg).Table(table)
    alerts: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {
        "KeyConditionExpression": Key("pk").eq(partition),
        "ScanIndexForward": False,
    }
    lek: dict[str, Any] | None = None

    try:
        while len(alerts) < max_items:
            q = dict(kwargs)
            q["Limit"] = min(100, max_items - len(alerts))
            if lek:
                q["ExclusiveStartKey"] = lek
            resp = tbl.query(**q)
            for it in resp.get("Items") or []:
                row = it.get("alert") if isinstance(it.get("alert"), dict) else None
                if row is None:
                    continue
                out = _jsonify_for_api(dict(row))
                if isinstance(it.get("prediction_s3_key"), str):
                    out["_prediction_s3_key"] = it["prediction_s3_key"]
                if isinstance(it.get("source_bucket"), str) or isinstance(it.get("source_key"), str):
                    out["_prediction_meta"] = {
                        "source_bucket": it.get("source_bucket") or "",
                        "source_key": it.get("source_key") or "",
                    }
                alerts.append(out)
            lek = resp.get("LastEvaluatedKey")
            if not lek:
                break
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"lecture alertes DynamoDB table={table} pk={partition}: {e}") from e

    return {
        "alerts": alerts,
        "count": len(alerts),
        "source": f"dynamodb://{table}/{partition}",
    }
