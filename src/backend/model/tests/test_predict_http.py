"""Test minimal de l'API ``POST /predict`` (liste d'événements → JSON ``alerts``)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE = "http://13.39.21.85:8080"


def predict_http(events: list[dict], *, base_url: str | None = None) -> dict:
    base = (base_url or os.getenv("PREDICT_BASE_URL", DEFAULT_BASE)).rstrip("/")
    url = f"{base}/predict"
    data = json.dumps({"events": events}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())


if __name__ == "__main__":
    sample = [
        {
            "timestamp": "2026-01-15T08:00:01Z",
            "log_source": "authentication",
            "source_ip": "203.0.113.50",
            "auth_method": "ssh",
            "status": "failure",
            "username": "root",
        },
        {
            "timestamp": "2026-01-15T08:00:02Z",
            "log_source": "authentication",
            "source_ip": "203.0.113.50",
            "auth_method": "ssh",
            "status": "failure",
            "username": "admin",
        },
        {
            "timestamp": "2026-01-15T08:00:03Z",
            "log_source": "authentication",
            "source_ip": "203.0.113.50",
            "auth_method": "ssh",
            "status": "failure",
            "username": "ubuntu",
        },
        {
            "timestamp": "2026-01-15T08:00:04Z",
            "log_source": "authentication",
            "source_ip": "203.0.113.50",
            "auth_method": "ssh",
            "status": "failure",
            "username": "test",
        },
        {
            "timestamp": "2026-01-15T08:00:05Z",
            "log_source": "authentication",
            "source_ip": "203.0.113.50",
            "auth_method": "ssh",
            "status": "failure",
            "username": "oracle",
        },
    ]
    base = os.getenv("PREDICT_BASE_URL", DEFAULT_BASE).rstrip("/")
    try:
        out = predict_http(sample)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read().decode(errors='replace')}") from e
    except urllib.error.URLError as e:
        hint = (
            f"Aucune réponse depuis {base}/predict ({e.reason}). "
            "Lance l’API du modèle (port 8080), ou définis PREDICT_BASE_URL vers une instance qui tourne.\n"
            "Exemple local : depuis la racine du repo,\n"
            "  PYTHONPATH=src python3 -m uvicorn backend.model.serve_app:app --host 127.0.0.1 --port 8080\n"
            "ou : ./src/backend/scripts/run_model_serve.sh"
        )
        raise SystemExit(hint) from e
    print(json.dumps(out, ensure_ascii=False, indent=2))
