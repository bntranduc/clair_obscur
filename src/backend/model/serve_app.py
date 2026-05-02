"""API minimale : événements normalisés → ``predict_alerts`` (Bedrock)."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.model.bedrock_client import MODEL_ID_DEFAULT
from backend.model.predict import predict_alerts

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
