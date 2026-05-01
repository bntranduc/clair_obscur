"""
API FastAPI minimale : fenêtre de logs (``NormalizedEvent`` en dicts) → règles + Bedrock → alertes style ground truth DS1.
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.model.bedrock_client import MODEL_ID_DEFAULT
from backend.model.incident_llm import DEFAULT_ALLOWED_ATTACK_TYPES, predict_submission_from_incidents
from backend.model.rules.aggregate_signals import aggregate_signals
from backend.model.rules.rules_window import detect_signals_window_1h

app = FastAPI(title="clair-obscur-model", version="0.1.0")


class PredictRequest(BaseModel):
    """Liste d'événements déjà normalisés (mêmes clés que ``NormalizedEvent``)."""

    events: list[dict[str, Any]] = Field(..., min_length=1)


class PredictResponse(BaseModel):
    """Alertes au format « hit » OpenSearch comme ``datasets/ground_truth_ds1.json``."""

    alerts: list[dict[str, Any]]


def llm_item_to_ground_truth_hit(item: dict[str, Any]) -> dict[str, Any]:
    """Transforme une entrée renvoyée par ``predict_submission_from_incidents`` en document type DS1."""
    det = item.get("detection") or {}
    attack_type = str(det.get("attack_type") or item.get("challenge_id") or "unknown")
    cid = str(item.get("challenge_id") or attack_type)
    _source: dict[str, Any] = {
        "dataset": 1,
        "challenge_id": cid,
        "attack_type": attack_type,
        "attacker_ips": list(det.get("attacker_ips") or []),
        "victim_accounts": list(det.get("victim_accounts") or []),
        "attack_window": {
            "start": str(det.get("attack_start_time") or "1970-01-01T00:00:00Z"),
            "end": str(det.get("attack_end_time") or "1970-01-01T00:00:00Z"),
        },
        "indicators": dict(det.get("indicators") or {}),
        "sources_needed": [],
        "points_max": 0,
    }
    return {
        "_index": "ground-truth-ds1",
        "_id": attack_type,
        "_score": None,
        "_source": _source,
        "sort": [attack_type],
    }


def predictions_to_alerts(pred: Any) -> list[dict[str, Any]]:
    if pred is None:
        return []
    rows = pred if isinstance(pred, list) else [pred]
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if "detection" not in row:
            continue
        out.append(llm_item_to_ground_truth_hit(row))
    return out


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    signals = detect_signals_window_1h(req.events)
    incidents = aggregate_signals(signals)
    if not incidents:
        return PredictResponse(alerts=[])

    model_id = (os.getenv("BEDROCK_MODEL_ID") or "").strip() or MODEL_ID_DEFAULT
    max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "4096"))
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-3"))

    try:
        pred = predict_submission_from_incidents(
            incidents,
            allowed_attack_types=DEFAULT_ALLOWED_ATTACK_TYPES,
            region=region,
            model_id=model_id,
            max_tokens=max_tokens,
        )
    except (json.JSONDecodeError, ValueError):
        # Réponse LLM vide ou JSON illisible (prompt demande parfois « rien »).
        return PredictResponse(alerts=[])
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return PredictResponse(alerts=predictions_to_alerts(pred))
