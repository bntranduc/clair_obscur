#!/usr/bin/env python3
"""Lit un JSON (events ou hits `_source`), POST ``/predict`` sur ``model_api`` (même corps que curl).

  MODEL_API_URL          défaut http://13.39.21.85:8080
  AWS_ACCESS_KEY_ID      obligatoire
  AWS_SECRET_ACCESS_KEY  obligatoire
  AWS_SESSION_TOKEN      optionnel (STS)

  python3 test_model_endpoint_from_file.py chemin/vers/fichier.json
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("MODEL_API_URL", "http://13.39.21.85:8080").rstrip("/")
TIMEOUT = int(os.environ.get("PREDICT_TIMEOUT_SEC", "300"))


def _events(raw: object) -> list:
    if isinstance(raw, dict) and "events" in raw:
        return list(raw["events"])
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "_source" in raw[0]:
        return [h["_source"] for h in raw if isinstance(h, dict) and "_source" in h]
    if isinstance(raw, list):
        return raw
    sys.exit("JSON attendu: {\"events\": [...]} ou liste d’objets / hits _source")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"fichier introuvable: {path}", file=sys.stderr)
        return 2
    ak = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    sk = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    if not ak or not sk:
        print("export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY (et AWS_SESSION_TOKEN si STS)", file=sys.stderr)
        return 2

    events = _events(json.loads(path.read_text(encoding="utf-8")))
    body: dict = {"events": events, "aws_access_key_id": ak, "aws_secret_access_key": sk}
    tok = os.environ.get("AWS_SESSION_TOKEN", "").strip()
    if tok:
        body["aws_session_token"] = tok

    req = urllib.request.Request(
        f"{BASE}/predict",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            print(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(e.reason, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
