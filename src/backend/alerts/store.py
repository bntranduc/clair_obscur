"""Charge les alertes depuis un fichier JSON (remplaçable plus tard par une vraie base)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    # .../src/backend/alerts/store.py → parents[3] = racine du dépôt
    return Path(__file__).resolve().parents[3]


def alerts_json_path() -> Path:
    """Chemin du fichier d’alertes. Surcharge : env ``ALERTS_DATASET_PATH`` (absolu ou relatif à la racine du dépôt)."""
    env = (os.getenv("ALERTS_DATASET_PATH") or "").strip()
    if env:
        p = Path(env)
        if p.is_absolute():
            return p
        return _repo_root() / p
    return _repo_root() / "database" / "alerts.json"


def load_all_alerts() -> dict[str, Any]:
    """
    Retourne ``{ "alerts": [...], "count": n }``.
    ``ALERTS_SOURCE=dynamodb`` → table alertes ; ``s3`` → bucket prédictions ; sinon fichier local.
    """
    source = (os.getenv("ALERTS_SOURCE") or "file").strip().lower()
    if source == "dynamodb":
        from backend.aws.dynamodb_alerts import load_all_alerts_from_dynamodb

        return load_all_alerts_from_dynamodb()
    if source == "s3":
        from backend.alerts.s3_predictions import load_alerts_from_predictions_bucket

        return load_alerts_from_predictions_bucket()

    path = alerts_json_path()
    if not path.is_file():
        raise FileNotFoundError(f"Fichier d'alertes introuvable : {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    alerts = raw.get("alerts")
    if not isinstance(alerts, list):
        raise ValueError("Le JSON d'alertes doit contenir une clé « alerts » (tableau).")
    return {
        "alerts": alerts,
        "count": len(alerts),
        "source_path": str(path),
    }
