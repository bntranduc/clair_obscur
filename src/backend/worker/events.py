from __future__ import annotations

import gzip
import json
from typing import Any
from urllib.parse import unquote_plus

from backend.log.normalization.normalize import normalize


def jsonl_gz_to_events(raw_bytes: bytes, *, key: str) -> list[dict[str, Any]]:
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


def parse_s3_records(body: str) -> list[tuple[str, str]]:
    try:
        envelope = json.loads(body)
    except json.JSONDecodeError:
        return []
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
