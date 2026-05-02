"""Charge tous les fichiers de prédictions S3 et agrège les alertes JSON."""

from __future__ import annotations

import json
import os
from typing import Any

import boto3

BUCKET_PREDICTIONS_PROD = "model-attacks-predictions"
BUCKET_PREDICTIONS_TMP = "model-attacks-predictions-tmp"
# Par défaut : bucket tmp (export ``PREDICTIONS_BUCKET`` ou arg ``bucket=`` pour prod).
DEFAULT_ALERTS_BUCKET = BUCKET_PREDICTIONS_TMP
DEFAULT_ALERTS_PREFIX = "predictions/"


def _s3_session(region: str, profile_name: str | None):
    session = boto3.Session(profile_name=profile_name) if profile_name else boto3.Session()
    return session.client("s3", region_name=region)


def _scan_bucket_alerts(
    *,
    bucket: str | None = None,
    prefix: str | None = None,
    region: str | None = None,
    profile_name: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retourne (liste d’alertes dict, statistiques de parcours)."""
    b = bucket or os.getenv("PREDICTIONS_BUCKET", DEFAULT_ALERTS_BUCKET).strip()
    pfx = prefix or os.getenv("PREDICTIONS_PREFIX", DEFAULT_ALERTS_PREFIX).strip() or DEFAULT_ALERTS_PREFIX
    if not pfx.endswith("/"):
        pfx += "/"
    reg = region or os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
    prof = (
        profile_name
        if profile_name is not None
        else (os.getenv("AWS_PROFILE", "").strip() or None)
    )
    s3 = _s3_session(reg, prof)

    out: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "bucket": b,
        "prefix": pfx,
        "region": reg,
        "objects_seen": 0,
        "objects_skipped_folder_marker": 0,
        "json_decode_errors": 0,
        "body_not_object": 0,
        "alerts_key_missing_or_not_list": 0,
        "files_with_empty_alerts": 0,
        "files_with_alert_items": 0,
        "non_dict_alert_items_skipped": 0,
        "sample_meta_keys": None,
    }

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=b, Prefix=pfx):
        for meta in page.get("Contents") or []:
            key = meta["Key"]
            if key.endswith("/"):
                stats["objects_skipped_folder_marker"] += 1
                continue
            stats["objects_seen"] += 1
            raw = s3.get_object(Bucket=b, Key=key)["Body"].read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                stats["json_decode_errors"] += 1
                continue
            if not isinstance(body, dict):
                stats["body_not_object"] += 1
                continue
            if stats["sample_meta_keys"] is None and isinstance(body.get("meta"), dict):
                stats["sample_meta_keys"] = list(body["meta"].keys())

            alerts = body.get("alerts")
            if not isinstance(alerts, list):
                stats["alerts_key_missing_or_not_list"] += 1
                continue
            if len(alerts) == 0:
                stats["files_with_empty_alerts"] += 1
            else:
                stats["files_with_alert_items"] += 1
            for a in alerts:
                if isinstance(a, dict):
                    out.append(a)
                else:
                    stats["non_dict_alert_items_skipped"] += 1

    return out, stats


def fetch_all_alerts_from_s3(
    *,
    bucket: str | None = None,
    prefix: str | None = None,
    region: str | None = None,
    profile_name: str | None = None,
) -> list[dict[str, Any]]:
    """Liste tous les objets sous ``prefix``, lit chaque JSON (champ ``alerts``),
    renvoie la concaténation des alertes (dict uniquement).

    Les fichiers produits par le worker peuvent être petits (~200 o) avec
    ``"alerts": []`` et un ``meta`` (ex. ``no_events_parsed``) — dans ce cas
    la liste renvoyée est vide mais le scan est correct.

    Variables d’env : ``PREDICTIONS_BUCKET`` (sinon défaut **tmp** :
    ``model-attacks-predictions-tmp``), ``PREDICTIONS_PREFIX``, ``AWS_REGION``,
    ``AWS_PROFILE``.

    CLI : ``python -m backend.aws.s3.alerts`` (tmp), ``--prod`` ou ``--tmp``.
    """
    alerts, _ = _scan_bucket_alerts(
        bucket=bucket, prefix=prefix, region=region, profile_name=profile_name
    )
    return alerts


def print_all_alerts_from_s3(
    *,
    bucket: str | None = None,
    prefix: str | None = None,
    region: str | None = None,
    profile_name: str | None = None,
) -> None:
    """Récupère toutes les alertes, affiche un résumé de scan puis chaque alerte."""
    alerts, stats = _scan_bucket_alerts(
        bucket=bucket, prefix=prefix, region=region, profile_name=profile_name
    )
    print(
        f"s3://{stats['bucket']}/{stats['prefix']} (region={stats['region']})",
        flush=True,
    )
    print(
        "scan: "
        f"objects={stats['objects_seen']}, "
        f"empty_alert_files={stats['files_with_empty_alerts']}, "
        f"files_with_items={stats['files_with_alert_items']}, "
        f"json_errors={stats['json_decode_errors']}, "
        f"alerts_not_list={stats['alerts_key_missing_or_not_list']}",
        flush=True,
    )
    if stats["sample_meta_keys"]:
        print(f"meta keys (1er fichier vu): {stats['sample_meta_keys']}", flush=True)
    print(f"total alerts (dicts): {len(alerts)}", flush=True)
    for i, a in enumerate(alerts, 1):
        print(f"\n--- #{i} ---", flush=True)
        print(json.dumps(a, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    import sys

    bucket: str | None = None
    if "--prod" in sys.argv:
        bucket = BUCKET_PREDICTIONS_PROD
    elif "--tmp" in sys.argv:
        bucket = BUCKET_PREDICTIONS_TMP
    print_all_alerts_from_s3(bucket=bucket)
