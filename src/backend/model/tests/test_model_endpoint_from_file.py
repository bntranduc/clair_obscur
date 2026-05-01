"""POST /predict avec le jeu SSH brute-force (fichier local) → modèle déployé.

Définir PREDICT_API_URL avec la base HTTP de l’API (sans slash final), ex. :
  export PREDICT_API_URL=http://ec2-xx-xx-xx-xx.compute.amazonaws.com:8080
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[4]
_DATA = _REPO / "datasets/dataset_test/attacks/opensearch_range_logs_ssh_bruteforce_plus2h.json"


def _predict_base_or_raise() -> str:
    base = os.getenv("PREDICT_API_URL", "").strip().rstrip("/")
    if not base:
        raise ValueError(
            "Set PREDICT_API_URL to your deployed predict API base "
            "(e.g. http://your-host:8080)"
        )
    return base


def _post_predict(events: list[Any]) -> str:
    base = _predict_base_or_raise()
    data = json.dumps({"events": events}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/predict",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode("utf-8", errors="replace")) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"{base}/predict: {e.reason!s}") from e


def test_predict_deployed_from_opensearch_file() -> None:
    if not _DATA.is_file():
        pytest.skip(f"missing dataset: {_DATA}")
    try:
        _predict_base_or_raise()
    except ValueError as e:
        pytest.skip(str(e))
    raw = json.loads(_DATA.read_text(encoding="utf-8"))
    events = [h["_source"] for h in raw if isinstance(h, dict) and "_source" in h]
    body = _post_predict(events)
    print(json.dumps(json.loads(body), indent=2, ensure_ascii=False))
    out = json.loads(body)
    assert "alerts" in out


if __name__ == "__main__":
    if not _DATA.is_file():
        raise SystemExit(f"missing dataset: {_DATA}")
    raw = json.loads(_DATA.read_text(encoding="utf-8"))
    events = [h["_source"] for h in raw if isinstance(h, dict) and "_source" in h]
    try:
        body = _post_predict(events)
    except (ValueError, RuntimeError) as e:
        raise SystemExit(str(e)) from e
    print(json.dumps(json.loads(body), indent=2, ensure_ascii=False))
