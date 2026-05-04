"""API HTTP : logs normalisés depuis S3 ou DynamoDB (voir ``backend.aws``)."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from botocore.exceptions import BotoCoreError, ClientError

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=False)

from backend.aws.dynamodb_normalized_logs import (  # noqa: E402
    default_logs_partition_key,
    fetch_normalized_page_from_dynamodb,
)
from backend.aws.s3.logs import fetch_normalized_page  # noqa: E402
from backend.analytics.dynamodb_dashboard import (  # noqa: E402
    DYNAMODB_ANALYTICS_MAX_ITEMS_CAP,
    get_dynamodb_dashboard,
)
from backend.analytics.siem import get_siem_dashboard  # noqa: E402
from api.agentic_router import router as agentic_router  # noqa: E402
from api.chat_router import router as chat_router  # noqa: E402

API_V1 = "/api/v1"


def _analytics_time_bounds(since: str | None, until: str | None) -> tuple[str | None, str | None]:
    """``since`` / ``until`` : paire obligatoire si l’un est renseigné ; ISO 8601 ; ``since`` ≤ ``until``."""
    s_raw = (since or "").strip()
    u_raw = (until or "").strip()
    if bool(s_raw) ^ bool(u_raw):
        raise HTTPException(
            status_code=400,
            detail="Les paramètres « since » et « until » doivent être fournis ensemble ou absents tous les deux.",
        )
    if not s_raw:
        return None, None
    try:
        ds = datetime.fromisoformat(s_raw.replace("Z", "+00:00"))
        du = datetime.fromisoformat(u_raw.replace("Z", "+00:00"))
    except (TypeError, ValueError, OSError) as e:
        raise HTTPException(status_code=400, detail="« since » ou « until » n’est pas une date ISO 8601 valide.") from e
    if ds > du:
        raise HTTPException(status_code=400, detail="« since » doit être antérieur ou égal à « until ».")
    return s_raw, u_raw


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


@app.get(f"{API_V1}/logs/dynamodb")
def normalized_logs_dynamodb(
    limit: int = Query(50, ge=1, le=500),
    pk: str | None = Query(
        None,
        description="Clé de partition ; sinon DYNAMODB_LOGS_PK, DYNAMODB_PK, DYNAMODB_LOGS_DAY ou défaut (cf. test.py).",
    ),
    start_key: str | None = Query(
        None,
        description="Curseur : repasser ``next_start_key`` de la page précédente.",
    ),
    region: str | None = Query(None, description="Région AWS (DynamoDB) ; défaut env / eu-west-3."),
) -> dict[str, Any]:
    """Logs normalisés depuis DynamoDB. Identifiants AWS : **uniquement** rôle IAM / ``.env`` du serveur (pas de clés en query)."""
    pk_resolved = (
        (pk or "").strip()
        or os.getenv("DYNAMODB_LOGS_PK", "").strip()
        or os.getenv("DYNAMODB_PK", "").strip()
        or default_logs_partition_key()
    )
    try:
        items, has_more, next_cursor = fetch_normalized_page_from_dynamodb(
            pk=pk_resolved,
            limit=limit,
            start_key=(start_key or "").strip() or None,
            region=(region or "").strip() or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (ClientError, BotoCoreError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {
        "items": items,
        "has_more": has_more,
        "next_start_key": next_cursor,
        "limit": limit,
        "pk": pk_resolved,
    }


@app.get(f"{API_V1}/analytics/siem")
def siem_analytics(
    hours: int = Query(24, ge=1, le=168),
    since: str | None = Query(None, description="ISO 8601 — avec « until », fenêtre fixe au lieu du glissant « hours »."),
    until: str | None = Query(None, description="ISO 8601 — borne haute (incluse dans les agrégations)."),
) -> dict[str, Any]:
    """KPIs et séries pour le tableau de bord SIEM (agrégations OpenSearch, repli démo si besoin)."""
    s, u = _analytics_time_bounds(since, until)
    return get_siem_dashboard(hours=hours, since=s, until=u)


@app.get(f"{API_V1}/analytics/dynamodb")
def analytics_dynamodb(
    max_items: int = Query(15_000, ge=100, le=DYNAMODB_ANALYTICS_MAX_ITEMS_CAP),
    pk: str | None = Query(None, description="Partition DynamoDB ; sinon env / défaut (cf. logs DynamoDB)."),
    region: str | None = Query(None, description="Région AWS."),
    since: str | None = Query(
        None,
        description="ISO 8601 — avec « until », filtre en mémoire sur ``timestamp`` du log (après chargement de ``max_items`` lignes).",
    ),
    until: str | None = Query(
        None,
        description="ISO 8601 — borne haute inclusive sur ``timestamp`` du log (après chargement de ``max_items`` lignes).",
    ),
    timeline_granularity: Literal["hour", "minute"] = Query(
        "hour",
        description="Agrégation de la chronologie : ``hour`` (par heure UTC) ou ``minute`` (par minute UTC).",
    ),
) -> dict[str, Any]:
    """Métriques et séries : lecture des ``max_items`` derniers éléments de la partition, puis filtre période optionnel."""
    pk_resolved = (
        (pk or "").strip()
        or os.getenv("DYNAMODB_LOGS_PK", "").strip()
        or os.getenv("DYNAMODB_PK", "").strip()
        or default_logs_partition_key()
    )
    s, u = _analytics_time_bounds(since, until)
    try:
        return get_dynamodb_dashboard(
            pk=pk_resolved,
            max_items=max_items,
            region=(region or "").strip() or None,
            since=s,
            until=u,
            timeline_granularity=timeline_granularity,
        )
    except (ClientError, BotoCoreError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
