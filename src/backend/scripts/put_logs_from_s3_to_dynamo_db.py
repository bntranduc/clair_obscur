#!/usr/bin/env python3
"""
Parcourt S3 (clair-obscure-raw-logs), normalise chaque ligne, PutItem dans DynamoDB
table normalized-logs avec pk, sk, id, event.

Usage (depuis la racine du repo, ex. ~/clair_obscur) :
  export AWS_PROFILE=bao
  export AWS_REGION=eu-west-3
  export RAW_LOGS_PREFIX='raw/opensearch/logs-raw/'   # adapter
  PYTHONPATH=src python3 src/backend/scripts/put_logs_from_s3_to_dynamo_db.py

Optionnel : export DRY_RUN=1  (ne fait que compter / afficher un échantillon)
"""
from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal

# Racine repo : …/src/backend/scripts → parents[3]
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, os.path.join(_REPO, "src"))

import boto3
from backend.aws.s3.logs import iter_normalized_events

BUCKET = os.getenv("RAW_LOGS_BUCKET", "clair-obscure-raw-logs").strip()
PREFIX = os.getenv("RAW_LOGS_PREFIX", "raw/opensearch/logs-raw/").strip()
REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
TABLE = os.getenv("DYNAMODB_TABLE", "normalized-logs")
DRY_RUN = os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}


def _day_from_ts(ts: str | None) -> str:
    if not ts or len(ts) < 10:
        return "unknown"
    return ts[:10]


def _stable_id(s3_key: str, line: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{s3_key}:{line}"))


def _ddb_document(v):  # Types natifs pour Table.put_item (float → Decimal)
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, dict):
        return {k: _ddb_document(x) for k, x in v.items() if x is not None}
    if isinstance(v, list):
        return [_ddb_document(x) for x in v if x is not None]
    return v


def main() -> None:
    sts = boto3.client("sts", region_name=REGION)
    ident = sts.get_caller_identity()
    arn = (ident.get("Arn") or "")[:140]
    print(
        f"[cible] Account={ident.get('Account')} Arn={arn}{'…' if len(ident.get('Arn') or '') > 140 else ''}\n"
        f"[cible] region={REGION} table={TABLE} bucket={BUCKET} prefix={PREFIX}",
        flush=True,
    )
    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)
    n_ok = 0
    n_err = 0

    for ev in iter_normalized_events(bucket=BUCKET, prefix=PREFIX, region=REGION):
        raw_ref = ev.get("raw_ref") or {}
        s3_key = str(raw_ref.get("s3_key") or "")
        line = int(raw_ref.get("line") or 0)
        log_id = _stable_id(s3_key, line)

        ts = ev.get("timestamp")
        ts_str = ts if isinstance(ts, str) and ts else "1970-01-01T00:00:00Z"
        day = _day_from_ts(ts_str)

        pk = f"RAW#{BUCKET}#D#{day}"
        sk = f"{ts_str}#{log_id}"

        item = {
            "pk": pk,
            "sk": sk,
            "id": log_id,
            "s3_key": s3_key,
            "line": line,
            "event": _ddb_document(dict(ev)),
        }

        if DRY_RUN:
            if n_ok < 2:
                print("EXEMPLE", pk, sk, log_id)
            n_ok += 1
            continue

        try:
            table.put_item(Item=item)
            n_ok += 1
            if n_ok % 500 == 0:
                print(f"... {n_ok} écrits", flush=True)
        except Exception as e:  # noqa: BLE001
            n_err += 1
            print("ERR", e, "pk=", pk, "sk=", sk[:80], file=sys.stderr)
            if n_err > 20:
                print("Trop d'erreurs, arrêt.", file=sys.stderr)
                break

    print(
        f"Terminé : {n_ok} items traités, {n_err} erreurs (DRY_RUN={DRY_RUN}).\n"
        "Si la console DynamoDB affiche encore 0 : même compte AWS que ci-dessus ? "
        "Métriques « nombre d’éléments » peuvent être retardées — utiliser « Explorer les éléments de la table ».",
        flush=True,
    )


if __name__ == "__main__":
    main()