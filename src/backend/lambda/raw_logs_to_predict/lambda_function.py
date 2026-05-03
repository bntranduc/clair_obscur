"""
Lambda : événement SQS (notification S3) → lecture JSONL/gzip → POST /predict (model_api)
→ écriture JSON dans OUTPUT_BUCKET.

Variables d'environnement :
  MODEL_API_URL       Base URL (ex. http://13.39.21.85:8080) — obligatoire
  OUTPUT_BUCKET       Défaut alerts-predictions
  OUTPUT_PREFIX       Défaut predictions/
  PREDICT_TIMEOUT_SEC Timeout HTTP (secondes), défaut 120

Handler : lambda_function.lambda_handler
Runtime conseillé : Python 3.12 (boto3 déjà fourni).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote_plus
from urllib.request import Request, urlopen

import boto3

# Aligné sur backend.log.normalization.normalize (champs attendus par le modèle)
_ALL_FIELDS: Tuple[str, ...] = (
    "timestamp",
    "log_source",
    "action",
    "auth_method",
    "bytes_received",
    "bytes_sent",
    "destination_ip",
    "destination_port",
    "duration_ms",
    "facility",
    "failure_reason",
    "geolocation_country",
    "geolocation_lat",
    "geolocation_lon",
    "hostname",
    "http_method",
    "message",
    "packets",
    "pid",
    "process",
    "protocol",
    "referer",
    "response_size",
    "response_time_ms",
    "session_id",
    "severity",
    "source_ip",
    "source_port",
    "status",
    "status_code",
    "uri",
    "user_agent",
    "username",
)


def _normalize_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: raw.get(k) for k in _ALL_FIELDS}
    if "raw_ref" in raw and isinstance(raw.get("raw_ref"), dict):
        out["raw_ref"] = raw["raw_ref"]
    return out


def _jsonl_gz_to_events(raw_bytes: bytes, *, key: str) -> List[Dict[str, Any]]:
    if key.endswith(".gz"):
        raw_bytes = gzip.decompress(raw_bytes)
    text = raw_bytes.decode("utf-8", errors="replace")
    events: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "_source" in obj:
            raw = obj["_source"]
        elif isinstance(obj, dict):
            raw = obj
        else:
            continue
        if not isinstance(raw, dict):
            continue
        events.append(_normalize_event(dict(raw)))
    return events


def _parse_s3_records(body: str) -> List[Tuple[str, str]]:
    try:
        envelope = json.loads(body)
    except json.JSONDecodeError:
        return []
    if isinstance(envelope, dict) and "Message" in envelope and "TopicArn" in envelope:
        try:
            inner = envelope.get("Message")
            envelope = json.loads(inner) if isinstance(inner, str) else {}
        except (json.JSONDecodeError, TypeError):
            return []
    records = envelope.get("Records") if isinstance(envelope, dict) else None
    if not isinstance(records, list):
        return []
    out: List[Tuple[str, str]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        s3 = rec.get("s3")
        if not isinstance(s3, dict):
            continue
        b = s3.get("bucket") or {}
        o = s3.get("object") or {}
        name = b.get("name") if isinstance(b, dict) else None
        key = o.get("key") if isinstance(o, dict) else None
        if isinstance(name, str) and isinstance(key, str):
            out.append((name, unquote_plus(key)))
    return out


def _output_key(source_bucket: str, source_key: str) -> str:
    prefix = os.getenv("OUTPUT_PREFIX", "predictions/").strip() or "predictions/"
    if not prefix.endswith("/"):
        prefix += "/"
    h = hashlib.sha256(f"{source_bucket}/{source_key}".encode()).hexdigest()[:24]
    safe = source_key.replace("/", "_").replace(" ", "_")
    if len(safe) > 180:
        safe = safe[:180]
    return f"{prefix}{h}_{safe}.json"


def _lambda_creds_payload() -> Dict[str, str]:
    c = boto3.Session().get_credentials()
    if c is None:
        raise RuntimeError("no AWS credentials in Lambda context")
    fr = c.get_frozen_credentials()
    payload: Dict[str, str] = {
        "aws_access_key_id": fr.access_key,
        "aws_secret_access_key": fr.secret_key,
    }
    if fr.token:
        payload["aws_session_token"] = fr.token
    return payload


def _post_model_predict(
    base_url: str,
    events: List[Dict[str, Any]],
    *,
    region: str,
    timeout: int,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/predict"
    body: Dict[str, Any] = {
        "events": events,
        **_lambda_creds_payload(),
    }
    if region:
        body["region"] = region
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _process_sqs_body(s3_client: Any, body: str) -> None:
    base = os.environ.get("MODEL_API_URL", "").strip()
    if not base:
        raise RuntimeError("MODEL_API_URL is required")

    out_bucket = os.getenv("OUTPUT_BUCKET", "alerts-predictions").strip()
    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()
    timeout = int(os.getenv("PREDICT_TIMEOUT_SEC", "120"))

    pairs = _parse_s3_records(body)
    if not pairs:
        raise ValueError("no S3 Records in SQS message body")

    for bucket, key in pairs:
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        raw_bytes = obj["Body"].read()
        events = _jsonl_gz_to_events(raw_bytes, key=key)
        out_key = _output_key(bucket, key)
        meta = {"source_bucket": bucket, "source_key": key, "event_count": len(events)}

        if not events:
            result: Dict[str, Any] = {"alerts": [], "meta": {**meta, "note": "no_events_parsed"}}
        else:
            result = _post_model_predict(base, events, region=region, timeout=timeout)
            if isinstance(result, dict):
                result = {**result, "meta": meta}

        s3_client.put_object(
            Bucket=out_bucket,
            Key=out_key,
            Body=json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3").strip()
    s3_client = boto3.client("s3", region_name=region)

    records = event.get("Records") or []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        body = rec.get("body", "")
        if not isinstance(body, str):
            body = str(body)
        _process_sqs_body(s3_client, body)

    return {"ok": True, "processed": len(records)}
