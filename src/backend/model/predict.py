"""Pipeline prédiction : règles → agrégation → Bedrock → alertes JSON."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from backend.aws.aws_client import AwsClient
from backend.log.normalization.types import NormalizedEvent
from backend.model.prompt.prompt import PREDICTION_PROMPT_TEMPLATE
from backend.model.rules.aggregate_signals import aggregate_signals
from backend.model.rules.rules_window import detect_signals_window_1h

MODEL_ID_DEFAULT = "eu.anthropic.claude-sonnet-4-6"

DEFAULT_ALLOWED_ATTACK_TYPES: tuple[str, ...] = (
    "ssh_brute_force",
    "credential_stuffing",
    "sql_injection",
    "directory_traversal",
    "ssrf",
    "exfiltration",
    "reconnaissance",
    "lfi_rfi",
    "credential_dumping",
    "log4shell",
    "sensitive_file_disclosure",
    "lfi_to_rce",
    "log4shell_rce",
    "credential_exfiltration",
)

SEVERITY_LEVELS_SIEM: tuple[str, ...] = ("low", "medium", "high", "critical")
DEFAULT_DETECTION_TIME_SECONDS = 300

_PROMPT_DIR = Path(__file__).resolve().parent / "prompt"


def _aws_client(
    *,
    region: str,
    profile_name: str | None = None,
    inline_credentials: dict[str, str] | None = None,
) -> AwsClient:
    if inline_credentials:
        ak = (inline_credentials.get("aws_access_key_id") or "").strip()
        sk = (inline_credentials.get("aws_secret_access_key") or "").strip()
        if not ak or not sk:
            raise ValueError("inline_credentials requires aws_access_key_id and aws_secret_access_key")
        creds: dict[str, str] = {"aws_access_key_id": ak, "aws_secret_access_key": sk}
        st = (inline_credentials.get("aws_session_token") or "").strip()
        if st:
            creds["aws_session_token"] = st
        return AwsClient(region_name=region, credentials=creds)
    prof = profile_name if profile_name is not None else os.getenv("AWS_PROFILE")
    prof = (prof or "").strip() or None
    return AwsClient(region_name=region, profile_name=prof)


def _bedrock_text(
    prompt: str,
    *,
    region: str,
    model_id: str,
    max_tokens: int,
    profile_name: str | None,
    inline_credentials: dict[str, str] | None,
) -> str:
    if not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    client = _aws_client(
        region=region,
        profile_name=profile_name,
        inline_credentials=inline_credentials,
    ).bedrock_runtime()
    resp = client.converse(
        modelId=(model_id or MODEL_ID_DEFAULT).strip(),
        messages=[{"role": "user", "content": [{"text": prompt.strip()}]}],
        inferenceConfig={"maxTokens": int(max_tokens)},
    )
    parts = resp.get("output", {}).get("message", {}).get("content", [])
    texts: list[str] = []
    if isinstance(parts, list):
        for p in parts:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                texts.append(p["text"])
    return "".join(texts).strip()


def _format_embedded_prediction_examples() -> str:
    p1 = _PROMPT_DIR / "expected_predictions_example.json"
    p2 = _PROMPT_DIR / "expected_predictions_second_type_example.json"
    ex1 = json.loads(p1.read_text(encoding="utf-8"))
    ex2 = json.loads(p2.read_text(encoding="utf-8"))
    s1 = json.dumps(ex1, ensure_ascii=False, indent=2)
    s2 = json.dumps(ex2, ensure_ascii=False, indent=2)
    return f"""Example 1 — full object shape (fictional values; attack_type ssh_brute_force):
{s1}

Example 2 — same shape, different attack_type (credential_stuffing, fictional):
{s2}"""


def _slice_balanced_json(text: str, start: int, open_ch: str, close_ch: str) -> str | None:
    if start < 0 or start >= len(text) or text[start] != open_ch:
        return None
    depth = 0
    i = start
    n = len(text)
    in_str = False
    esc = False
    while i < n:
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            i += 1
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    return None


def _extract_json_value(text: str) -> Any:
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()

    arr_start = t.find("[")
    obj_start = t.find("{")
    if arr_start != -1 and (obj_start == -1 or arr_start < obj_start):
        blob = _slice_balanced_json(t, arr_start, "[", "]")
        if blob:
            return json.loads(blob)
    if obj_start != -1:
        blob = _slice_balanced_json(t, obj_start, "{", "}")
        if blob:
            return json.loads(blob)
    raise ValueError("Model response did not contain a parseable JSON value")


def build_prediction_prompt(
    *,
    aggregated_incidents: Sequence[Mapping[str, Any]],
    allowed_attack_types: Iterable[str],
    detection_time_seconds: int = DEFAULT_DETECTION_TIME_SECONDS,
) -> str:
    types_list = "\n".join(f"- {x}" for x in allowed_attack_types)
    incidents_blob = json.dumps(list(aggregated_incidents), ensure_ascii=False, indent=2)
    examples_blob = _format_embedded_prediction_examples()
    return PREDICTION_PROMPT_TEMPLATE.format(
        types_list=types_list,
        detection_time_seconds=detection_time_seconds,
        examples_blob=examples_blob,
        incidents_blob=incidents_blob,
    )


def _normalize_alerts(out: Any) -> list[dict[str, Any]]:
    if isinstance(out, list):
        return [x for x in out if isinstance(x, dict)]
    if isinstance(out, dict):
        return [out]
    raise RuntimeError(f"LLM returned unexpected type: {type(out).__name__}")


def predict_from_incidents(
    aggregated_incidents: Sequence[Mapping[str, Any]],
    *,
    allowed_attack_types: Sequence[str] | None = None,
    detection_time_seconds: int = DEFAULT_DETECTION_TIME_SECONDS,
    region: str = "eu-west-3",
    model_id: str = MODEL_ID_DEFAULT,
    max_tokens: int = 4096,
    profile_name: str | None = None,
    inline_aws_credentials: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Appelle Bedrock sur des incidents déjà agrégés."""
    allowed = tuple(allowed_attack_types or DEFAULT_ALLOWED_ATTACK_TYPES)
    prompt = build_prediction_prompt(
        aggregated_incidents=aggregated_incidents,
        allowed_attack_types=allowed,
        detection_time_seconds=detection_time_seconds,
    )
    raw = _bedrock_text(
        prompt,
        region=region,
        model_id=model_id,
        max_tokens=max_tokens,
        profile_name=profile_name,
        inline_credentials=dict(inline_aws_credentials) if inline_aws_credentials else None,
    )
    return _normalize_alerts(_extract_json_value(raw))


def predict_alerts(
    events: Sequence[NormalizedEvent],
    *,
    region: str = "eu-west-3",
    model_id: str | None = None,
    max_tokens: int = 4096,
    profile_name: str | None = None,
    inline_aws_credentials: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Règles → agrégation → Bedrock."""
    incidents = aggregate_signals(detect_signals_window_1h(events))
    try:
        return predict_from_incidents(
            incidents,
            region=region,
            model_id=(model_id or MODEL_ID_DEFAULT).strip(),
            max_tokens=max_tokens,
            profile_name=profile_name,
            inline_aws_credentials=inline_aws_credentials,
        )
    except Exception as exc:
        raise RuntimeError("LLM prediction failed") from exc
