#!/usr/bin/env python3
"""
Charge ``datasets/dataset_test/dataset_test_full.json`` (hits OpenSearch) et appelle
``predict_alerts`` (règles + Bedrock).

Le fichier peut être très volumineux : utilise ``LIMIT`` pour ne traiter que les N
premiers enregistrements.

Prérequis : ``pip install python-dotenv`` (optionnel), ``aws sso login`` si profil SSO.

Usage (depuis la racine du repo) ::
    PYTHONPATH=src LIMIT=5000 python3 src/backend/scripts/run_dataset_test_full.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "src"))

from dotenv import load_dotenv  # noqa: E402

from backend.log.normalization.normalize import normalize  # noqa: E402
from backend.model.predict import predict_alerts  # noqa: E402

_DEFAULT_DATA = _REPO / "datasets/dataset_test/dataset_test_full.json"

load_dotenv(_REPO / ".env", override=True)


def main() -> int:
    path = Path(os.getenv("DATASET_TEST_FULL_JSON", _DEFAULT_DATA))
    limit_raw = os.getenv("LIMIT", "5000").strip()
    limit = int(limit_raw) if limit_raw else 0

    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        print("expected JSON array of hits", file=sys.stderr)
        return 2

    events = []
    for i, rec in enumerate(rows):
        if limit and i >= limit:
            break
        raw = rec.get("_source", rec) if isinstance(rec, dict) else rec
        rid = rec.get("_id", "") if isinstance(rec, dict) else ""
        events.append(normalize(raw, {"raw_id": rid, "file": str(path), "line": i}))

    print(f"events: {len(events)} (limit={limit or 'none'})", file=sys.stderr)
    alerts = predict_alerts(events)
    print(json.dumps(alerts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
