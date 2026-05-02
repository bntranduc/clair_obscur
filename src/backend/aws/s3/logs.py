"""Liste tous les logs bruts S3 (JSONL / gzip) → événements normalisés."""

from __future__ import annotations

import gzip
import io
import json
import os

import boto3

from backend.log.normalization.normalize import normalize
from backend.log.normalization.types import NormalizedEvent


def fetch_all_normalized_logs(
    *,
    bucket: str | None = None,
    prefix: str | None = None,
    region: str | None = None,
    profile_name: str | None = None,
) -> list[NormalizedEvent]:
    """Parcourt tout le préfixe S3, lit chaque fichier ligne à ligne, normalise.

    Utilise ``RAW_LOGS_BUCKET``, ``RAW_LOGS_PREFIX``, ``AWS_REGION``,
    ``AWS_PROFILE`` si les arguments sont omis.

    Charge l'intégralité des événements en mémoire — éviter sur des buckets énormes.
    """
    b = bucket or os.getenv("RAW_LOGS_BUCKET", "clair-obscure-raw-logs").strip()
    pfx = prefix or os.getenv("RAW_LOGS_PREFIX", "raw/opensearch/logs-raw/").strip()
    reg = region or os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
    prof = (
        profile_name
        if profile_name is not None
        else (os.getenv("AWS_PROFILE", "").strip() or None)
    )
    session = boto3.Session(profile_name=prof) if prof else boto3.Session()
    s3 = session.client("s3", region_name=reg)

    out: list[NormalizedEvent] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=b, Prefix=pfx):
        for meta in page.get("Contents") or []:
            key = meta["Key"]
            if key.endswith("/"):
                continue
            raw = s3.get_object(Bucket=b, Key=key)["Body"].read()
            buf = io.BytesIO(raw)
            if key.endswith(".gz"):
                text = io.TextIOWrapper(
                    gzip.GzipFile(fileobj=buf), encoding="utf-8", errors="replace"
                )
            else:
                text = io.TextIOWrapper(buf, encoding="utf-8", errors="replace")
            try:
                n = 0
                for line in text:
                    n += 1
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(row, dict):
                        continue
                    src = row["_source"] if "_source" in row else row
                    if not isinstance(src, dict):
                        continue
                    out.append(normalize(src, raw_ref={"s3_key": key, "line": n}))
            finally:
                text.close()

    return out
