"""API modèle : événements normalisés → ``predict_alerts`` (Bedrock uniquement).

- **Avec** ``aws_credentials`` dans le corps : Bedrock avec ces identifiants pour cette requête.
- **Sans** : Bedrock via ``AWS_PROFILE`` / rôle instance / variables d’environnement AWS.

Expose aussi ``/api/v1/analytics/siem`` (même contrat que ``api.main``) pour un déploiement
où le front cible cette instance (ex. port 8080) au lieu de ``api.main``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if load_dotenv is not None:
    load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=False)

from api.agent_catalog import build_agent_catalog  # noqa: E402
from api.agentic_bridge import _repo_root  # noqa: E402
from api.agentic_router import router as agentic_router  # noqa: E402
from api.chat_router import router as chat_router  # noqa: E402
from backend.agentic.config.loader import load_config  # noqa: E402
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
app.include_router(chat_router)
app.include_router(agentic_router)


@app.get(f"{API_V1}/agents/catalog")
def agents_catalog_alias() -> dict[str, Any]:
    """Même contenu que ``GET /api/v1/agentic/catalog`` (alias si proxy / ancien routage)."""
    return build_agent_catalog(load_config(_repo_root()))


class InlineAwsCredentials(BaseModel):
    """Identifiants AWS pour un seul ``POST /predict`` → appel Bedrock (STS recommandé).

    À utiliser avec parcimonie : tout secret dans le corps d’une requête peut fuiter (logs applicatifs,
    reverse proxy, traces APM). Préférer un rôle IAM sur l’instance lorsque Bedrock est joignable.
    """

    aws_access_key_id: str = Field(..., min_length=8)
    aws_secret_access_key: str = Field(..., min_length=8)
    aws_session_token: str | None = Field(
        default=None,
        description="Requis pour les sessions temporaires STS.",
        min_length=4,
    )
    region: str | None = Field(
        default=None,
        min_length=3,
        description="Si renseigné : région AWS pour cet appel Bedrock (remplace AWS_REGION pour cette requête).",
    )

    @field_validator("aws_session_token", mode="before")
    @classmethod
    def empty_token_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class PredictRequest(BaseModel):
    events: list[dict[str, Any]] = Field(..., min_length=1)
    aws_credentials: InlineAwsCredentials | None = Field(
        default=None,
        description="Optionnel : Bedrock avec ces identifiants pour cette requête ; sinon identifiants ambiant (profil / rôle).",
    )


class PredictResponse(BaseModel):
    alerts: list[dict[str, Any]]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))
    if req.aws_credentials and req.aws_credentials.region:
        region = (req.aws_credentials.region or "").strip() or region
    mid = (os.getenv("BEDROCK_MODEL_ID") or "").strip() or MODEL_ID_DEFAULT
    max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "4096"))
    prof = (os.getenv("AWS_PROFILE") or "").strip() or None

    inline_creds: dict[str, str] | None = None
    if req.aws_credentials is not None:
        d = req.aws_credentials.model_dump()
        d.pop("region", None)
        inline_creds = {k: str(v) for k, v in d.items() if v is not None}

    try:
        alerts = predict_alerts(
            req.events,
            region=region,
            model_id=mid,
            max_tokens=max_tokens,
            profile_name=None if inline_creds else prof,
            inline_aws_credentials=inline_creds,
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
