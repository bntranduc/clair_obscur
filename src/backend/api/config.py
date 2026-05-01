"""Configuration partagée des endpoints API (variables d'environnement)."""

from __future__ import annotations

import os

API_V1_PREFIX = "/api/v1"

RAW_BUCKET = os.getenv("RAW_LOGS_BUCKET", "clair-obscure-raw-logs").strip()
RAW_PREFIX = os.getenv("RAW_LOGS_PREFIX", "raw/opensearch/logs-raw/").strip()
REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))

CORS_ORIGINS = [o.strip() for o in os.getenv("DASHBOARD_CORS_ORIGINS", "*").split(",") if o.strip()]

# Prédictions modèle (S3) — aligné sur ``sqs_predict_worker`` / ``get_model_attacks_preds_from_s3``.
PREDICTIONS_BUCKET = os.getenv("PREDICTIONS_BUCKET", "model-attacks-predictions").strip()
PREDICTIONS_BUCKET_TMP = os.getenv("PREDICTIONS_BUCKET_TMP", "model-attacks-predictions-tmp").strip()
PREDICTIONS_PREFIX = (
    os.getenv("PREDICTIONS_PREFIX", os.getenv("S3_PREFIX", "predictions/")).strip() or "predictions/"
)
if not PREDICTIONS_PREFIX.endswith("/"):
    PREDICTIONS_PREFIX += "/"
