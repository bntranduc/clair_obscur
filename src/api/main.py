"""API HTTP minimale : logs normalisés depuis S3 (voir ``backend.aws.s3.logs``)."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

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


@app.get(f"{API_V1}/logs/normalized")
def normalized_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """Paginate les événements normalisés (ordre S3 : objets récents d’abord)."""
    items, has_more = fetch_normalized_page(skip=skip, limit=limit)
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
