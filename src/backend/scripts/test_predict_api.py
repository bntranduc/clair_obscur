#!/usr/bin/env python3
"""POST /predict avec les logs OpenSearch du jeu de test SSH brute-force."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_DEFAULT_HITS = _REPO / "datasets/dataset_test/attacks/opensearch_range_logs_ssh_bruteforce_plus2h.json"


def main() -> int:
    base = os.getenv("PREDICT_API_URL", "http://127.0.0.1:8080").rstrip("/")
    path = Path(os.getenv("PREDICT_LOG_JSON", _DEFAULT_HITS))
    raw = json.loads(path.read_text(encoding="utf-8"))
    events = [h["_source"] for h in raw if isinstance(h, dict) and "_source" in h]
    data = json.dumps({"events": events}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/predict",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            print(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
