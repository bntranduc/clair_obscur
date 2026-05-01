"""Configuration partagée des endpoints API (variables d'environnement)."""

from __future__ import annotations

import os

API_V1_PREFIX = "/api/v1"

RAW_BUCKET = os.getenv("RAW_LOGS_BUCKET", "clair-obscure-raw-logs").strip()
RAW_PREFIX = os.getenv("RAW_LOGS_PREFIX", "raw/opensearch/logs-raw/").strip()
REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))

def get_cors_origins() -> list[str]:
    """Origines CORS pour le dashboard.

    Si ``DASHBOARD_CORS_ORIGINS`` liste des URLs (sans ``*``), on ajoute par défaut
    ``localhost:3000`` pour pouvoir tester ``npm run dev`` contre l’API sur EC2.
    Utiliser ``DASHBOARD_CORS_STRICT=1`` pour désactiver cet ajout en prod stricte.
    """
    raw = os.getenv("DASHBOARD_CORS_ORIGINS")
    if raw is None:
        return ["*"]
    s = raw.strip()
    if s == "" or s == "*":
        return ["*"]
    out = [x.strip() for x in s.split(",") if x.strip()]
    if os.getenv("DASHBOARD_CORS_STRICT", "").strip() == "1":
        return out
    for dev in ("http://localhost:3000", "http://127.0.0.1:3000"):
        if dev not in out:
            out.append(dev)
    return out

# Prédictions modèle (sortie worker SQS → JSON dans S3, voir ``sqs_predict_worker``).
PREDICTIONS_BUCKET_MAIN = os.getenv("MODEL_PREDICTIONS_BUCKET", "model-attacks-predictions").strip()
PREDICTIONS_BUCKET_TMP = os.getenv("MODEL_PREDICTIONS_BUCKET_TMP", "model-attacks-predictions-tmp").strip()
PREDICTIONS_PREFIX = os.getenv("MODEL_PREDICTIONS_PREFIX", "predictions/").strip()
