"""API FastAPI minimale pour EC2 : ``POST /predict`` → Bedrock uniquement.

Le corps de la requête contient les événements normalisés **et** des identifiants AWS
(``aws_access_key_id``, ``aws_secret_access_key``, ``aws_session_token`` optionnel pour
clés longue durée) utilisés **uniquement** pour cet appel Bedrock (``AwsClient``).

**Sécurité** : ne jamais logger le corps ; préférer ensuite un rôle IAM sur l’instance si
Bedrock est joignable sans STS dans le HTTP.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from backend.model.bedrock_client import MODEL_ID_DEFAULT
from backend.model.predict import predict_alerts

app = FastAPI(title="clair-obscur-model-api", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    events: List[Dict[str, Any]] = Field(..., min_length=1)
    aws_access_key_id: str = Field(..., min_length=4)
    aws_secret_access_key: str = Field(..., min_length=4)
    aws_session_token: Optional[str] = Field(
        default=None,
        description="Jeton STS ; omis pour une paire clé secrète IAM classique.",
    )
    region: Optional[str] = Field(
        default=None,
        description="Région Bedrock pour cet appel (sinon AWS_REGION / eu-west-3).",
    )

    @field_validator("aws_session_token", mode="before")
    @classmethod
    def _blank_session_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class PredictResponse(BaseModel):
    alerts: List[Dict[str, Any]]


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    region = (
        (req.region or "").strip()
        or os.getenv("AWS_REGION", "").strip()
        or os.getenv("AWS_DEFAULT_REGION", "").strip()
        or "eu-west-3"
    )
    mid = (os.getenv("BEDROCK_MODEL_ID") or "").strip() or MODEL_ID_DEFAULT
    max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "4096"))

    inline: dict[str, str] = {
        "aws_access_key_id": req.aws_access_key_id.strip(),
        "aws_secret_access_key": req.aws_secret_access_key.strip(),
    }
    if req.aws_session_token:
        inline["aws_session_token"] = req.aws_session_token.strip()

    try:
        alerts = predict_alerts(
            req.events,
            region=region,
            model_id=mid,
            max_tokens=max_tokens,
            profile_name=None,
            inline_aws_credentials=inline,
        )
    except (json.JSONDecodeError, ValueError):
        return PredictResponse(alerts=[])
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return PredictResponse(alerts=alerts)
