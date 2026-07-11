from __future__ import annotations

from typing import Any, Literal, Sequence

from backend.log.normalization.types import NormalizedEvent
from backend.model.api_client import API_MODEL_ID_DEFAULT
from backend.model.bedrock_client import MODEL_ID_DEFAULT
from backend.model.incident_llm import DEFAULT_ALLOWED_ATTACK_TYPES, predict_submission_from_incidents
from backend.model.rules.aggregate_signals import aggregate_signals
from backend.model.rules.rules_window import detect_signals_window_1h


def predict_alerts(
    events: Sequence[NormalizedEvent],
    *,
    backend: Literal["bedrock", "api"] = "bedrock",
    # bedrock
    region: str = "eu-west-3",
    model_id: str | None = None,
    max_tokens: int = 4096,
    profile_name: str | None = None,
    inline_aws_credentials: dict[str, str] | None = None,
    # direct api
    api_key: str | None = None,
    api_model_id: str = API_MODEL_ID_DEFAULT,
) -> list[dict[str, Any]]:
    """Règles → agrégation → LLM obligatoire (Bedrock ou API). Aucun repli sans appel modèle."""
    incidents = aggregate_signals(detect_signals_window_1h(events))
    try:
        out = predict_submission_from_incidents(
            incidents,
            backend=backend,
            allowed_attack_types=DEFAULT_ALLOWED_ATTACK_TYPES,
            region=region,
            model_id=model_id or MODEL_ID_DEFAULT,
            max_tokens=max_tokens,
            profile_name=profile_name,
            inline_aws_credentials=inline_aws_credentials,
            api_key=api_key,
            api_model_id=api_model_id,
        )
    except Exception as exc:
        raise RuntimeError("LLM prediction failed") from exc

    if isinstance(out, list):
        return [x for x in out if isinstance(x, dict)]
    if isinstance(out, dict):
        return [out]
    raise RuntimeError(f"LLM returned unexpected type: {type(out).__name__}")
