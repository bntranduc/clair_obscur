from __future__ import annotations

import os
from typing import Any, Literal, Sequence

from backend.log.normalization.types import NormalizedEvent
from backend.model.api_client import API_MODEL_ID_DEFAULT
from backend.model.bedrock_client import MODEL_ID_DEFAULT
from backend.model.incident_llm import DEFAULT_ALLOWED_ATTACK_TYPES, predict_submission_from_incidents
from backend.model.rules.aggregate_signals import aggregate_signals
from backend.model.rules.rules_window import detect_signals_window_1h

# rule_id → attack_type pour séparer les alertes en mode démo VM
_RULE_ATTACK_TYPE: dict[str, str] = {
    "SQL_INJECTION": "sql_injection",
    "SQL_INJECTION_SQLMAP_UA": "sql_injection",
    "SQL_INJECTION_MANY_500": "sql_injection",
    "SQL_INJECTION_EXFIL": "sql_injection",
    "WEB_SQLI_AUTOMATED": "sql_injection",
    "SSRF": "ssrf",
    "DIRECTORY_TRAVERSAL": "directory_traversal",
    "DIRECTORY_TRAVERSAL_SUCCESS": "directory_traversal",
    "WEB_SENSITIVE_FILE_ACCESS": "directory_traversal",
    "WEB_LFI_RFI": "lfi_rfi",
    "SSH_BRUTEFORCE": "ssh_brute_force",
    "SSH_BRUTEFORCE_SSH_ONLY": "ssh_brute_force",
    "SSH_PRIV_ESC": "ssh_brute_force",
    "CREDENTIAL_STUFFING": "credential_stuffing",
    "WEB_BRUTEFORCE_HTTP": "credential_stuffing",
    "WEB_BRUTEFORCE_HTTP_UA": "credential_stuffing",
}


def _demo_mode_enabled() -> bool:
    return (os.getenv("RULES_DEMO_MODE") or "").strip().lower() in ("1", "true", "yes", "on")


def _bucket_incidents_for_demo(incidents: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for inc in incidents:
        rule = str(inc.get("rule_id") or "")
        attack_type = _RULE_ATTACK_TYPE.get(rule)
        if not attack_type:
            continue
        buckets.setdefault(attack_type, []).append(inc)
    return buckets


def _normalize_llm_output(out: Any) -> list[dict[str, Any]]:
    if isinstance(out, list):
        return [x for x in out if isinstance(x, dict)]
    if isinstance(out, dict):
        return [out]
    raise RuntimeError(f"LLM returned unexpected type: {type(out).__name__}")


def _call_llm(
    incidents: list[dict[str, Any]],
    *,
    backend: Literal["bedrock", "api"],
    region: str,
    model_id: str | None,
    max_tokens: int,
    profile_name: str | None,
    inline_aws_credentials: dict[str, str] | None,
    api_key: str | None,
    api_model_id: str,
) -> list[dict[str, Any]]:
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
    return _normalize_llm_output(out)


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
    llm_kwargs = dict(
        backend=backend,
        region=region,
        model_id=model_id,
        max_tokens=max_tokens,
        profile_name=profile_name,
        inline_aws_credentials=inline_aws_credentials,
        api_key=api_key,
        api_model_id=api_model_id,
    )
    try:
        # Mode démo : une alerte LLM par type d'attaque (SQLi, SSRF, traversal…) au lieu d'une seule fusionnée.
        if _demo_mode_enabled():
            buckets = _bucket_incidents_for_demo(incidents)
            if len(buckets) >= 2:
                merged: list[dict[str, Any]] = []
                for _attack_type, bucket in buckets.items():
                    merged.extend(_call_llm(bucket, **llm_kwargs))
                if merged:
                    return merged
        return _call_llm(incidents, **llm_kwargs)
    except Exception as exc:
        raise RuntimeError("LLM prediction failed") from exc
