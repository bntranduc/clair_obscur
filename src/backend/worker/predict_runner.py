from __future__ import annotations

import json
import urllib.request
from typing import Any


def post_predict(base: str, events: list[dict[str, Any]], *, timeout: int) -> dict[str, Any]:
    url = f"{base.rstrip('/')}/predict"
    payload = json.dumps({"events": events}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def predict_inline(
    events: list[dict[str, Any]],
    *,
    region: str,
    model_id: str | None,
    max_tokens: int,
    profile_name: str | None,
) -> dict[str, Any]:
    from backend.model.predict import predict_alerts

    mid = (model_id or "").strip() or None
    alerts = predict_alerts(
        events,
        region=region,
        model_id=mid,
        max_tokens=max_tokens,
        profile_name=profile_name,
    )
    return {"alerts": alerts}


def run_predict(
    events: list[dict[str, Any]],
    *,
    mode: str,
    predict_base: str,
    predict_timeout: int,
    region: str,
    model_id: str | None,
    max_tokens: int,
    profile_name: str | None,
) -> dict[str, Any]:
    m = (mode or "http").strip().lower()
    if m == "http":
        return post_predict(predict_base, events, timeout=predict_timeout)
    if m == "inline":
        return predict_inline(
            events,
            region=region,
            model_id=model_id,
            max_tokens=max_tokens,
            profile_name=profile_name,
        )
    raise ValueError(f"unknown PREDICT_MODE={mode!r} (use inline or http)")
