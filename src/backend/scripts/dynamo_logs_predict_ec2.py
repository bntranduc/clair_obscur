#!/usr/bin/env python3
"""2000 derniers logs DynamoDB → POST ``/predict`` sur l’API modèle EC2 → affiche les alertes.

URL de l’API modèle : constante ``MODEL_API_BASE`` ci‑dessous (à adapter).

Prérequis (identique à ``test.py`` / dashboard) :
  export AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=…  # (+ AWS_SESSION_TOKEN si STS)
  # ou : export AWS_PROFILE=…

  export DYNAMODB_TABLE=normalized-logs           # optionnel
  export DYNAMODB_PK=RAW#…                        # ou défaut via default_logs_partition_key

Usage (racine du dépôt) :
  PYTHONPATH=src python3 src/backend/scripts/dynamo_logs_predict_ec2.py

Optionnel : ``PREDICT_LIMIT=500`` (nombre max d’événements à envoyer, défaut 2000).

Référence ``curl`` (même ``POST /predict``, mêmes champs JSON que ce script ; exporter
``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_SESSION_TOKEN`` avant ; ``<<EOF``
sans quotes pour que bash substitue ``${…}``)::

  curl -sS -X POST "http://13.39.21.85:8080/predict" \\
    -H "Content-Type: application/json" \\
    -d @- <<EOF
  {
    "events": [
      {"timestamp":"2026-01-15T08:00:00Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"root","raw_ref":{"raw_id":"ssh-1"}},
      {"timestamp":"2026-01-15T08:00:02Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"admin","raw_ref":{"raw_id":"ssh-2"}},
      {"timestamp":"2026-01-15T08:00:04Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"ubuntu","raw_ref":{"raw_id":"ssh-3"}},
      {"timestamp":"2026-01-15T08:00:06Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"git","raw_ref":{"raw_id":"ssh-4"}},
      {"timestamp":"2026-01-15T08:00:08Z","log_source":"authentication","source_ip":"203.0.113.50","auth_method":"ssh","status":"failure","username":"deploy","raw_ref":{"raw_id":"ssh-5"}},
      {"timestamp":"2026-01-15T08:05:00Z","log_source":"application","source_ip":"198.51.100.9","hostname":"web-prod-01","uri":"/api?q=1+union+all+select+1,null--","http_method":"GET","status_code":200,"raw_ref":{"raw_id":"sqli-1"}},
      {"timestamp":"2026-01-15T08:05:01Z","log_source":"application","source_ip":"198.51.100.9","hostname":"web-prod-01","uri":"/search?id=%27+or+%271%27%3D%271","http_method":"GET","status_code":200,"raw_ref":{"raw_id":"sqli-2"}},
      {"timestamp":"2026-01-15T08:05:02Z","log_source":"application","source_ip":"198.51.100.9","hostname":"web-prod-01","uri":"/v2?q=1%27+UNION+SELECT+@@version--","http_method":"GET","status_code":500,"raw_ref":{"raw_id":"sqli-3"}}
    ],
    "aws_access_key_id": "${AWS_ACCESS_KEY_ID}",
    "aws_secret_access_key": "${AWS_SECRET_ACCESS_KEY}",
    "aws_session_token": "${AWS_SESSION_TOKEN}"
  }
  EOF
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, os.path.join(_REPO, "src"))

from backend.aws.dynamodb_normalized_logs import (  # noqa: E402
    default_logs_partition_key,
    fetch_normalized_page_from_dynamodb,
)

# À adapter : base HTTP(S) de l’API ``model_api`` sur EC2 (sans slash final).
MODEL_API_BASE = "http://13.39.21.85:8080"


def _fetch_last_events(*, pk: str, total: int, region: str | None, table: str | None) -> list[dict]:
    out: list[dict] = []
    cursor: str | None = None
    while len(out) < total:
        chunk = min(1000, total - len(out))
        batch, has_more, next_cursor = fetch_normalized_page_from_dynamodb(
            pk=pk,
            limit=chunk,
            start_key=cursor,
            region=region,
            table_name=table,
        )
        out.extend(batch)
        if not has_more or not next_cursor:
            break
        cursor = next_cursor
    return out


def main() -> int:
    base = MODEL_API_BASE.rstrip("/")
    timeout = int(os.environ.get("PREDICT_TIMEOUT_SEC", "600"))
    limit = 100_000
    if limit < 1:
        print("PREDICT_LIMIT doit être >= 1", file=sys.stderr)
        return 2

    ak = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    sk = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    if not ak or not sk:
        print(
            "DynamoDB + Bedrock via l’API : export AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY "
            "(+ AWS_SESSION_TOKEN si besoin).",
            file=sys.stderr,
        )
        return 2

    pk = (os.getenv("DYNAMODB_LOGS_PK") or os.getenv("DYNAMODB_PK") or "").strip() or default_logs_partition_key()
    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "").strip() or None
    table = (os.getenv("DYNAMODB_TABLE") or "").strip() or None

    print(f"Lecture DynamoDB pk={pk!r} (max {limit} événements)…", file=sys.stderr)
    events = _fetch_last_events(pk=pk, total=limit, region=region, table=table)
    if not events:
        print("Aucun événement renvoyé par DynamoDB.", file=sys.stderr)
        return 1
    print(f"{len(events)} événement(s) → POST {base}/predict …", file=sys.stderr)

    body: dict = {"events": events, "aws_access_key_id": ak, "aws_secret_access_key": sk}
    tok = os.environ.get("AWS_SESSION_TOKEN", "").strip()
    if tok:
        body["aws_session_token"] = tok
    reg = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "").strip()
    if reg:
        body["region"] = reg

    req = urllib.request.Request(
        f"{base}/predict",
        data=json.dumps(body, default=str).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(e.reason, file=sys.stderr)
        return 1

    alerts = data.get("alerts") if isinstance(data, dict) else None
    if not isinstance(alerts, list):
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        return 0

    print(json.dumps(alerts, indent=2, ensure_ascii=False, default=str))
    print(f"\n--- {len(alerts)} alerte(s) ---", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
