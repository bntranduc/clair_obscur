"""Proxy vers l'API modèle (FastAPI ``serve_app``, ``POST /predict``)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api import config

router = APIRouter(tags=["model"])


class PredictProxyRequest(BaseModel):
    """Même corps que ``backend.model.serve_app.PredictRequest``."""

    events: list[dict[str, Any]] = Field(..., min_length=1)


@router.post("/predict")
def proxy_predict(req: PredictProxyRequest) -> dict[str, Any]:
    """Transmet ``events`` au service modèle et renvoie son JSON (ex. ``alerts``)."""
    base = config.predict_api_base_url()
    url = f"{base}/predict"
    payload = json.dumps({"events": req.events}).encode("utf-8")
    http_req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_req, timeout=config.PREDICT_PROXY_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            detail: Any = json.loads(body)
        except json.JSONDecodeError:
            detail = body
        raise HTTPException(status_code=e.code, detail=detail) from e
    except urllib.error.URLError as e:
        raise HTTPException(
            status_code=502,
            detail=f"model API unreachable ({url}): {e.reason!s}",
        ) from e

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="model returned non-JSON") from exc
