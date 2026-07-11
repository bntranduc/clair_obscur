from __future__ import annotations

import os
from typing import Any, Literal, Sequence

from backend.log.normalization.types import NormalizedEvent
from backend.model.api_client import API_MODEL_ID_DEFAULT
from backend.model.bedrock_client import MODEL_ID_DEFAULT
from backend.model.incident_llm import DEFAULT_ALLOWED_ATTACK_TYPES, predict_submission_from_incidents
from backend.model.rules.aggregate_signals import aggregate_signals
from backend.model.rules.rules_window import detect_signals_window_1h


def _rules_kwargs_from_env() -> dict[str, Any]:
    """Seuils assouplis pour la VM démo / petits batches (curls manuels espacés)."""
    flag = (os.getenv("RULES_DEMO_MODE") or "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return {}
    return {
        "sqli_min_hits": 1,
        "ssrf_min_hits": 1,
        "traversal_min_hits": 1,
        "ssh_failures_threshold": 15,
        "ssh_exclusive_min_failures": 15,
        "http_bruteforce_threshold": 5,
        "dir_bruteforce_threshold": 10,
    }


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
    incidents = aggregate_signals(detect_signals_window_1h(events, **_rules_kwargs_from_env()))
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
