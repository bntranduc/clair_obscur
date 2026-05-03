"""Liste les logs bruts S3 (JSONL / gzip) → événements normalisés."""

from __future__ import annotations

import gzip
import io
import json
import os
from collections.abc import Iterator
from typing import Any

from backend.aws.aws_client import AwsClient
from backend.log.normalization.normalize import normalize
from backend.log.normalization.types import NormalizedEvent


def _s3_client(
    *,
    bucket: str | None,
    prefix: str | None,
    region: str | None,
    profile_name: str | None,
    credentials: dict[str, str] | None,
) -> tuple[Any, str, str]:
    b = bucket or os.getenv("RAW_LOGS_BUCKET", "clair-obscure-raw-logs").strip()
    pfx = prefix or os.getenv("RAW_LOGS_PREFIX", "raw/opensearch/logs-raw/").strip()
    reg = region or os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
    prof = (
        profile_name
        if profile_name is not None
        else ((os.getenv("AWS_PROFILE") or "").strip() or None)
    )
    aws = AwsClient(region_name=str(reg), profile_name=prof if not credentials else None, credentials=credentials)
    return aws.client("s3"), b, pfx


def iter_normalized_events(
    *,
    bucket: str | None = None,
    prefix: str | None = None,
    region: str | None = None,
    profile_name: str | None = None,
    credentials: dict[str, str] | None = None,
    newest_first: bool = True,
) -> Iterator[NormalizedEvent]:
    """Parcourt le préfixe S3 et produit un flux d’événements normalisés (un par ligne JSON valide).

    Ordre par défaut : objets S3 du plus récent au plus ancien, puis lignes dans chaque fichier.
    """
    s3, b, pfx = _s3_client(
        bucket=bucket,
        prefix=prefix,
        region=region,
        profile_name=profile_name,
        credentials=credentials,
    )
    metas: list[dict[str, Any]] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=b, Prefix=pfx):
        for meta in page.get("Contents") or []:
            key = meta["Key"]
            if key.endswith("/"):
                continue
            metas.append(meta)
    if newest_first:
        metas.sort(key=lambda m: m.get("LastModified") or 0, reverse=True)

    for meta in metas:
        key = meta["Key"]
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
                rid = row.get("_id", "")
                yield normalize(
                    src,
                    raw_ref={
                        "raw_id": str(rid) if rid is not None else "",
                        "s3_key": key,
                        "line": n,
                    },
                )
        finally:
            text.close()


def fetch_normalized_page(
    *,
    skip: int = 0,
    limit: int = 50,
    bucket: str | None = None,
    prefix: str | None = None,
    region: str | None = None,
    profile_name: str | None = None,
    credentials: dict[str, str] | None = None,
) -> tuple[list[NormalizedEvent], bool]:
    """Retourne une fenêtre paginée ``(items, has_more)`` sans charger tout le bucket."""
    if skip < 0:
        skip = 0
    if limit < 1:
        limit = 1

    out: list[NormalizedEvent] = []
    has_more = False
    idx = -1
    for ev in iter_normalized_events(
        bucket=bucket,
        prefix=prefix,
        region=region,
        profile_name=profile_name,
        credentials=credentials,
    ):
        idx += 1
        if idx < skip:
            continue
        if len(out) < limit:
            out.append(ev)
            continue
        has_more = True
        break

    return out, has_more


def fetch_all_normalized_logs(
    *,
    bucket: str | None = None,
    prefix: str | None = None,
    region: str | None = None,
    profile_name: str | None = None,
    credentials: dict[str, str] | None = None,
) -> list[NormalizedEvent]:
    """Parcourt tout le préfixe S3 — charge tout en mémoire (éviter sur des buckets énormes)."""
    return list(
        iter_normalized_events(
            bucket=bucket,
            prefix=prefix,
            region=region,
            profile_name=profile_name,
            credentials=credentials,
        )
    )
