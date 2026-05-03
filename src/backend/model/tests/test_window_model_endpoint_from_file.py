#!/usr/bin/env python3
"""Découpe les events par fenêtre (900 s par défaut), POST ``/predict`` par batch, concatène les ``alerts``.

  MODEL_API_URL          défaut http://13.39.21.85:8080
  WINDOW_SEC             largeur fenêtre (défaut 900)
  WINDOW_STEP_SEC        pas glissant (défaut = WINDOW_SEC → tuiles sans recouvrement ; ex. 300 pour chevauchement)
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN

  python3 test_window_model_endpoint_from_file.py chemin/vers/fichier.json
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = os.environ.get("MODEL_API_URL", "http://13.39.21.85:8080").rstrip("/")
TIMEOUT = int(os.environ.get("PREDICT_TIMEOUT_SEC", "300"))
W = int(os.environ.get("WINDOW_SEC", "900"))
STEP = int(os.environ.get("WINDOW_STEP_SEC", str(W)))


def _events(raw: object) -> list:
    if isinstance(raw, dict) and "events" in raw:
        return list(raw["events"])
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "_source" in raw[0]:
        return [h["_source"] for h in raw if isinstance(h, dict) and "_source" in h]
    if isinstance(raw, list):
        return raw
    sys.exit("JSON attendu: {\"events\": [...]} ou liste d’objets / hits _source")


def _ts(e: dict) -> float | None:
    t = e.get("timestamp")
    if not isinstance(t, str):
        return None
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
    except ValueError:
        return None


def _post(body: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}/predict",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


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
        print("export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY", file=sys.stderr)
        return 2

    events = _events(json.loads(path.read_text(encoding="utf-8")))
    pairs = [(e, t) for e in events if (t := _ts(e)) is not None]
    if not pairs:
        sys.exit("aucun event avec timestamp ISO valide")
    t_min = min(t for _, t in pairs)
    t_max = max(t for _, t in pairs)

    body_base: dict = {"aws_access_key_id": ak, "aws_secret_access_key": sk}
    if os.environ.get("AWS_SESSION_TOKEN", "").strip():
        body_base["aws_session_token"] = os.environ["AWS_SESSION_TOKEN"].strip()

    agg: list = []
    w = t_min
    while w < t_max + 1e-6:
        chunk = [e for e, t in pairs if w <= t < w + W]
        if chunk:
            try:
                out = _post({**body_base, "events": chunk})
                agg.extend(out.get("alerts") or [])
            except urllib.error.HTTPError as e:
                print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
                return 1
            except urllib.error.URLError as e:
                print(e.reason, file=sys.stderr)
                return 1
        w += STEP

    print(json.dumps({"alerts": agg}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
