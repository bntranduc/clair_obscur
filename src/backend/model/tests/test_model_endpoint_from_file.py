"""POST /predict avec le jeu SSH brute-force (fichier local) → API déployée (PREDICT_API_URL)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[4]
_DATA = _REPO / "datasets/dataset_test/attacks/opensearch_range_logs_ssh_bruteforce_plus2h.json"


def test_predict_deployed_from_opensearch_file() -> None:
    if not _DATA.is_file():
        pytest.skip(f"missing dataset: {_DATA}")
    raw = json.loads(_DATA.read_text(encoding="utf-8"))
    events = [h["_source"] for h in raw if isinstance(h, dict) and "_source" in h]
    base = os.getenv("PREDICT_API_URL", "http://127.0.0.1:8080").rstrip("/")
    data = json.dumps({"events": events}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/predict",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        pytest.fail(e.read().decode("utf-8", errors="replace"))
    print(json.dumps(json.loads(body), indent=2, ensure_ascii=False))
    out = json.loads(body)
    assert "alerts" in out
