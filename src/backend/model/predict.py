from __future__ import annotations

from typing import Any, Sequence

from backend.log.normalization.types import NormalizedEvent
from backend.model.bedrock_client import MODEL_ID_DEFAULT
from backend.model.incident_llm import DEFAULT_ALLOWED_ATTACK_TYPES, predict_submission_from_incidents
from backend.model.rules.aggregate_signals import aggregate_signals
from backend.model.rules.rules_window import detect_signals_window_1h


def predict_alerts(
    events: Sequence[NormalizedEvent],
    *,
    region: str = "eu-west-3",
    model_id: str | None = None,
    max_tokens: int = 4096,
    profile_name: str | None = None,
) -> list[dict[str, Any]]:
    incidents = aggregate_signals(detect_signals_window_1h(events))
    if not incidents:
        return []
    out = predict_submission_from_incidents(
        incidents,
        allowed_attack_types=DEFAULT_ALLOWED_ATTACK_TYPES,
        region=region,
        model_id=model_id or MODEL_ID_DEFAULT,
        max_tokens=max_tokens,
        profile_name=profile_name,
    )
    if isinstance(out, list):
        return [x for x in out if isinstance(x, dict)]
    if isinstance(out, dict):
        return [out]
    return []
