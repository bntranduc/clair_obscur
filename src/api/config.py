"""Variables d'environnement — S3 brut + profil AWS optionnel."""

from __future__ import annotations

import os

API_V1_PREFIX = "/api/v1"

RAW_BUCKET = os.getenv("RAW_LOGS_BUCKET", "clair-obscure-raw-logs").strip()
RAW_PREFIX = os.getenv("RAW_LOGS_PREFIX", "raw/opensearch/logs-raw/").strip()
REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))

# Prédictions / alertes — défaut tmp ; surcharge avec PREDICTIONS_BUCKET / _TMP dans .env pour prod.
PREDICTIONS_BUCKET = os.getenv("PREDICTIONS_BUCKET", "model-attacks-predictions-tmp").strip()
PREDICTIONS_BUCKET_TMP = os.getenv("PREDICTIONS_BUCKET_TMP", "model-attacks-predictions-tmp").strip()
PREDICTIONS_PREFIX = (
    os.getenv("PREDICTIONS_PREFIX", os.getenv("S3_PREFIX", "predictions/")).strip() or "predictions/"
)
if not PREDICTIONS_PREFIX.endswith("/"):
    PREDICTIONS_PREFIX += "/"

# Chaîne d'identifiants : si défini, boto3 utilise ce profil (~/.aws/config).
AWS_PROFILE = os.getenv("AWS_PROFILE", "").strip() or None

CORS_ORIGINS = [o.strip() for o in os.getenv("API_CORS_ORIGINS", "*").split(",") if o.strip()]

# Chat Bedrock (route ``/api/v1/chat``) — même profil IAM / SSO que le reste de l’API.
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "").strip() or None
BEDROCK_CHAT_MAX_TOKENS = int(os.getenv("BEDROCK_CHAT_MAX_TOKENS", "4096"))
BEDROCK_CHAT_SYSTEM_PROMPT = os.getenv("BEDROCK_CHAT_SYSTEM_PROMPT", "").strip()
