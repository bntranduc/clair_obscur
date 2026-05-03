"""API HTTP minimale : logs normalisés depuis S3 (voir ``backend.aws.s3.logs``)."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from botocore.exceptions import BotoCoreError, ClientError

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=False)

from backend.aws.s3.logs import fetch_normalized_page  # noqa: E402
from backend.analytics.siem import get_siem_dashboard  # noqa: E402
from api.agentic_router import router as agentic_router  # noqa: E402
from api.chat_router import router as chat_router  # noqa: E402

API_V1 = "/api/v1"

app = FastAPI(title="clair-obscur-api", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router)
app.include_router(agentic_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "clair-obscur-api"}


def _credentials_from_query(
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
    aws_session_token: str | None,
) -> dict[str, str] | None:
    """Identifiants inline pour S3 ; ``None`` si aucune clé (chaîne boto3 par défaut sur le serveur)."""
    ak = (aws_access_key_id or "").strip()
    sk = (aws_secret_access_key or "").strip()
    st = (aws_session_token or "").strip()
    if not ak and not sk:
        return None
    if not ak or not sk:
        raise ValueError(
            "AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY sont requis ensemble dans la requête."
        )
    out: dict[str, str] = {"aws_access_key_id": ak, "aws_secret_access_key": sk}
    if st:
        out["aws_session_token"] = st
    return out


@app.get(f"{API_V1}/logs/normalized")
def normalized_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    raw_logs_bucket: str | None = Query(None),
    raw_logs_prefix: str | None = Query(None),
    region: str | None = Query(None),
    AWS_ACCESS_KEY_ID: str | None = Query(None, description="Optionnel ; sinon rôle / env du serveur."),
    AWS_SECRET_ACCESS_KEY: str | None = Query(None, description="Optionnel ; à utiliser avec AWS_ACCESS_KEY_ID."),
    AWS_SESSION_TOKEN: str | None = Query(None, description="Optionnel (sessions STS)."),
) -> dict[str, Any]:
    """Paginate les événements normalisés. Identifiants AWS en **query** (mêmes noms que les variables d’env).

    Attention : les secrets apparaissent dans l’URL (logs serveur, historique). Préférer le rôle IAM quand possible.
    """
    try:
        creds = _credentials_from_query(
            AWS_ACCESS_KEY_ID,
            AWS_SECRET_ACCESS_KEY,
            AWS_SESSION_TOKEN,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        items, has_more = fetch_normalized_page(
            skip=skip,
            limit=limit,
            bucket=(raw_logs_bucket or "").strip() or None,
            prefix=(raw_logs_prefix or "").strip() or None,
            region=(region or "").strip() or None,
            credentials=creds,
        )
    except (ClientError, BotoCoreError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {
        "items": items,
        "has_more": has_more,
        "skip": skip,
        "limit": limit,
    }


@app.get(f"{API_V1}/analytics/siem")
def siem_analytics(hours: int = Query(24, ge=1, le=168)) -> dict[str, Any]:
    """KPIs et séries pour le tableau de bord SIEM (agrégations OpenSearch, repli démo si besoin)."""
    return get_siem_dashboard(hours=hours)
