import gzip
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # adds /.../src

from backend.log.normalization.normalize import normalize  # noqa: E402
from backend.model.rules.aggregate_signals import aggregate_signals  # noqa: E402
from backend.model.rules.rules_window import detect_signals_window_1h  # noqa: E402
from backend.model import DEFAULT_ALLOWED_ATTACK_TYPES, predict_submission_from_incidents  # noqa: E402


def _iter_records_from_s3_object(body: bytes, *, key: str) -> Iterable[dict[str, Any]]:
    raw = gzip.decompress(body) if key.endswith(".gz") else body
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    if text.lstrip().startswith("["):
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main() -> int:
    bucket = os.getenv("S3_BUCKET", "clair-obscure-raw-logs")
    prefix = os.getenv("S3_PREFIX", "raw/opensearch/logs-raw/")
    region = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "eu-west-3"))
    profile = os.getenv("AWS_PROFILE")

    session = boto3.Session(profile_name=profile, region_name=region) if profile else boto3.Session(region_name=region)
    s3 = session.client("s3")

    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    objs = resp.get("Contents", [])
    if not objs:
        raise SystemExit(f"No objects found under s3://{bucket}/{prefix}")
    objs.sort(key=lambda o: o["LastModified"], reverse=True)
    latest = objs[0]
    key = latest["Key"]

    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    records = list(_iter_records_from_s3_object(body, key=key))

    events = []
    for i, rec in enumerate(records):
        raw = rec.get("_source", rec) if isinstance(rec, dict) else rec
        raw_id = rec.get("_id", "") if isinstance(rec, dict) else ""
        events.append(normalize(raw, {"raw_id": raw_id, "s3_key": key, "line": i}))

    signals = detect_signals_window_1h(events)
    incidents = aggregate_signals(signals)

    if not incidents:
        # No incidents => no attack signal => print nothing (as requested).
        return 0

    pred = predict_submission_from_incidents(
        incidents,
        allowed_attack_types=DEFAULT_ALLOWED_ATTACK_TYPES,
    )
    print(json.dumps(pred, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
