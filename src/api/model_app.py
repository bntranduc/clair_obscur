"""API modèle : événements normalisés → ``predict_alerts`` (Bedrock).

Expose aussi ``/api/v1/analytics/siem`` (même contrat que ``api.main``) pour que le
dashboard fonctionne lorsque ``NEXT_PUBLIC_API_URL`` pointe vers cette instance (ex. port 8080).
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if load_dotenv is not None:
    load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=False)

from backend.model.bedrock_client import MODEL_ID_DEFAULT
from backend.model.predict import predict_alerts

API_V1 = "/api/v1"

app = FastAPI(title="clair-obscur-model", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    events: list[dict[str, Any]] = Field(..., min_length=1)


class PredictResponse(BaseModel):
    alerts: list[dict[str, Any]]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
    mid = (os.getenv("BEDROCK_MODEL_ID") or "").strip() or MODEL_ID_DEFAULT
    max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "4096"))
    prof = (os.getenv("AWS_PROFILE") or "").strip() or None
    try:
        alerts = predict_alerts(
            req.events,
            region=region,
            model_id=mid,
            max_tokens=max_tokens,
            profile_name=prof,
        )
    except (json.JSONDecodeError, ValueError):
        return PredictResponse(alerts=[])
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return PredictResponse(alerts=alerts)


@app.get(f"{API_V1}/analytics/siem")
def siem_analytics(hours: int = Query(24, ge=1, le=168)) -> dict[str, Any]:
    """KPIs et séries SIEM (OpenSearch, repli démo si besoin) — identique à ``api.main``."""
    try:
        from backend.analytics.siem import get_siem_dashboard
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                "Module analytics indisponible : installez les dépendances "
                "(ex. pip install -r src/api/requirements.txt, notamment opensearch-py)."
            ),
        ) from e
    return get_siem_dashboard(hours=hours)
