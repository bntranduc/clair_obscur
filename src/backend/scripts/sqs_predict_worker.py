#!/usr/bin/env python3
"""
Worker SQS → S3 (gzip JSONL) → POST /predict → S3 (résultat JSON).

Messages attendus : notifications S3 directes (corps JSON avec ``Records[]``).

Variables d'environnement :
  SQS_QUEUE_URL       URL de la file (obligatoire)
  PREDICT_API_URL     Base API, défaut http://127.0.0.1:8080
  OUTPUT_BUCKET       Défaut model-attacks-predictions
  OUTPUT_PREFIX       Défaut predictions/ (doit finir par /)
  AWS_REGION          Défaut eu-west-3
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus

_REPO = Path(__file__).resolve().parents[3]
_SRC = _REPO / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import boto3  # noqa: E402

from backend.log.normalization.normalize import normalize  # noqa: E402


def _jsonl_gz_to_events(raw_bytes: bytes, *, key: str) -> list[dict[str, Any]]:
    if key.endswith(".gz"):
        raw_bytes = gzip.decompress(raw_bytes)
    text = raw_bytes.decode("utf-8", errors="replace")
    events: list[dict[str, Any]] = []
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
        events.append(dict(normalize(raw)))
    return events


def _parse_s3_records(body: str) -> list[tuple[str, str]]:
    try:
        envelope = json.loads(body)
    except json.JSONDecodeError:
        return []
    # Enveloppe SNS → SQS (si jamais utilisé)
    if isinstance(envelope, dict) and "Message" in envelope and "TopicArn" in envelope:
        try:
            envelope = json.loads(envelope["Message"])
        except (json.JSONDecodeError, TypeError):
            return []
    records = envelope.get("Records") if isinstance(envelope, dict) else None
    if not isinstance(records, list):
        return []
    out: list[tuple[str, str]] = []
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


def _post_predict(base: str, events: list[dict[str, Any]], *, timeout: int) -> dict[str, Any]:
    url = f"{base.rstrip('/')}/predict"
    payload = json.dumps({"events": events}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _output_key(source_bucket: str, source_key: str) -> str:
    prefix = os.getenv("OUTPUT_PREFIX", "predictions/").strip() or "predictions/"
    if not prefix.endswith("/"):
        prefix += "/"
    h = hashlib.sha256(f"{source_bucket}/{source_key}".encode()).hexdigest()[:24]
    safe = source_key.replace("/", "_").replace(" ", "_")
    if len(safe) > 180:
        safe = safe[:180]
    return f"{prefix}{h}_{safe}.json"


def process_one_message(
    sqs: Any,
    s3: Any,
    queue_url: str,
    msg: dict[str, Any],
    *,
    predict_base: str,
    out_bucket: str,
    predict_timeout: int,
) -> None:
    body = msg.get("Body") or ""
    if not isinstance(body, str):
        body = str(body)
    pairs = _parse_s3_records(body)
    if not pairs:
        raise ValueError("no S3 Records in message body")
    receipt = msg["ReceiptHandle"]

    for bucket, key in pairs:
        obj = s3.get_object(Bucket=bucket, Key=key)
        raw_bytes = obj["Body"].read()
        events = _jsonl_gz_to_events(raw_bytes, key=key)
        out_key = _output_key(bucket, key)
        meta = {"source_bucket": bucket, "source_key": key, "event_count": len(events)}

        if not events:
            result: dict[str, Any] = {"alerts": [], "meta": {**meta, "note": "no_events_parsed"}}
        else:
            result = _post_predict(predict_base, events, timeout=predict_timeout)
            if isinstance(result, dict):
                result = {**result, "meta": meta}

        s3.put_object(
            Bucket=out_bucket,
            Key=out_key,
            Body=json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"wrote s3://{out_bucket}/{out_key}", flush=True)

    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)


def main() -> int:
    queue_url = os.getenv("SQS_QUEUE_URL", "").strip()
    if not queue_url:
        print("SQS_QUEUE_URL is required", file=sys.stderr)
        return 1

    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
    predict_base = os.getenv("PREDICT_API_URL", "http://127.0.0.1:8080").rstrip("/")
    out_bucket = os.getenv("OUTPUT_BUCKET", "model-attacks-predictions").strip()
    predict_timeout = int(os.getenv("PREDICT_TIMEOUT_SEC", "900"))
    wait_sec = int(os.getenv("SQS_WAIT_TIME_SECONDS", "20"))
    vis_timeout = int(os.getenv("SQS_VISIBILITY_TIMEOUT", "900"))

    session = boto3.session.Session(region_name=region)
    sqs = session.client("sqs")
    s3 = session.client("s3")

    print(
        f"worker start queue={queue_url!r} predict={predict_base} out={out_bucket}",
        flush=True,
    )
    while True:
        resp = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=min(20, max(0, wait_sec)),
            VisibilityTimeout=min(43200, max(0, vis_timeout)),
            AttributeNames=["All"],
        )
        messages = resp.get("Messages") or []
        if not messages:
            continue
        for msg in messages:
            try:
                process_one_message(
                    sqs,
                    s3,
                    queue_url,
                    msg,
                    predict_base=predict_base,
                    out_bucket=out_bucket,
                    predict_timeout=predict_timeout,
                )
            except urllib.error.HTTPError as e:
                print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
                print("HTTP error, message left for retry", file=sys.stderr)
            except Exception as e:
                print(f"error: {e}", file=sys.stderr)
                time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
